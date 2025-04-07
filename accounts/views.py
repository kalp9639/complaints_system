# accounts/views.py

from django.shortcuts import render, redirect
from django.contrib.auth import login, authenticate, logout
from django.contrib.auth.decorators import login_required
from django.utils.decorators import method_decorator
from django.utils import timezone
from django.contrib import messages
from django.views import View
from django.views.generic import FormView, TemplateView, ListView
from django.contrib.auth.views import LoginView, PasswordResetView, PasswordResetDoneView, PasswordResetConfirmView, PasswordResetCompleteView
from django.contrib.auth.models import User
from .forms import SignUpForm, UserUpdateForm
from django.urls import reverse_lazy, reverse
from django.contrib.auth import update_session_auth_hash
from .forms import SignUpForm, UserUpdateForm, PasswordChangeForm, UsernameOrEmailPasswordResetForm, CustomSetPasswordForm, OTPVerificationForm, MobileLoginForm, SocialMobileVerificationForm, OTPVerificationForm 
from .models import UserProfile
from .utils import send_verification_code, check_verification_code
from django.http import JsonResponse
from allauth.socialaccount.models import SocialAccount
from django.conf import settings 
from django.contrib.auth.tokens import default_token_generator
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode
from django.utils.html import strip_tags
from django.core.mail import EmailMultiAlternatives
from twilio.base.exceptions import TwilioRestException
from allauth.socialaccount.models import SocialAccount, SocialLogin
from django.contrib.auth import authenticate
import logging 

import logging
import json
from datetime import date, timedelta, datetime # Add datetime
from django.utils import timezone # Import timezone
from django.shortcuts import render, redirect
from django.views.generic import TemplateView
from django.db.models import Count, Q, Min, Avg, F, DurationField # Import Avg, F, DurationField
from django.db.models.functions import TruncDate, Cast # Import Cast
from complaints.models import Complaint
from authorities.models import ComplaintUpdate
from django.http import JsonResponse # For API endpoint
from django.urls import reverse 

logger = logging.getLogger(__name__)

def calculate_art_per_ward(complaints_queryset):
    """Calculates Average Resolution Time (in days) per ward for a given Complaint queryset."""
    art_data = {}
    try:
        # Get resolved complaints from the queryset
        resolved_complaints = complaints_queryset.filter(status='Resolved')

        # Find the first 'Resolved' update timestamp for each resolved complaint
        resolution_times = ComplaintUpdate.objects.filter(
            complaint__in=resolved_complaints,
            status='Resolved'
        ).values(
            'complaint_id', 'complaint__ward_number', 'complaint__created_at' # Include ward and created_at
        ).annotate(
            first_resolved_at=Min('updated_at')
        )

        # Calculate duration for each complaint
        durations = []
        for rt in resolution_times:
            if rt['first_resolved_at'] and rt['complaint__created_at']:
                # Ensure both are timezone-aware if USE_TZ=True
                created_at = rt['complaint__created_at']
                resolved_at = rt['first_resolved_at']
                # Make naive if necessary for subtraction, or ensure both are aware
                if timezone.is_aware(created_at) and not timezone.is_aware(resolved_at):
                     resolved_at = timezone.make_aware(resolved_at, timezone.get_default_timezone())
                elif not timezone.is_aware(created_at) and timezone.is_aware(resolved_at):
                     created_at = timezone.make_aware(created_at, timezone.get_default_timezone())

                duration = resolved_at - created_at
                if duration.total_seconds() > 0: # Ignore negative durations if any edge cases
                    durations.append({
                        'ward': rt['complaint__ward_number'],
                        'duration': duration
                    })

        # Group durations by ward
        ward_durations = {}
        for d in durations:
            ward = d['ward']
            if ward: # Only consider complaints with a ward
                if ward not in ward_durations:
                    ward_durations[ward] = []
                ward_durations[ward].append(d['duration'])

        # Calculate average duration per ward in days
        for ward, duration_list in ward_durations.items():
            if duration_list:
                avg_duration = sum(duration_list, timedelta()) / len(duration_list)
                art_data[ward] = round(avg_duration.total_seconds() / (60 * 60 * 24), 1) # Convert to days, 1 decimal

    except Exception as e:
        logger.error(f"Error calculating ART per ward: {e}", exc_info=True)

    # Sort by ward number (treating as numbers if possible)
    sorted_art_data = dict(sorted(art_data.items(), key=lambda item: int(item[0]) if item[0].isdigit() else float('inf')))

    return sorted_art_data
# --- End Helper Function ---


class HomeView(TemplateView):
    template_name = 'accounts/home.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        is_authenticated = user.is_authenticated
        is_official = hasattr(user, 'official_profile') if is_authenticated else False
        context['is_official'] = is_official

        # Shared definitions
        complaint_types_dict = dict(Complaint.COMPLAINT_TYPES)
        status_order = {'Pending': 0, 'In Progress': 1, 'Resolved': 2}

        # Initialize context variables
        context['user_data'] = {}
        context['overall_data'] = {}

        # --- 1. User-Specific Stats (Only for Logged-in Citizens) ---
        if is_authenticated and not is_official:
            user_complaints = Complaint.objects.filter(
                user=user,
                is_trashed=False,
                is_permanently_deleted=False
            )
            user_data = {}
            try:
                # User Type Doughnut
                type_counts = user_complaints.values('complaint_type').annotate(count=Count('id')).order_by('complaint_type')
                user_data['type_chart'] = {
                    'labels': [complaint_types_dict.get(item['complaint_type'], item['complaint_type'].capitalize()) for item in type_counts],
                    'values': [item['count'] for item in type_counts]
                }

                # User Status Doughnut
                status_counts = user_complaints.values('status').annotate(count=Count('id')).order_by('status')
                status_counts_sorted = sorted(status_counts, key=lambda x: status_order.get(x['status'], 99))
                user_data['status_chart'] = {
                    'labels': [item['status'] for item in status_counts_sorted],
                    'values': [item['count'] for item in status_counts_sorted]
                }

                # User Grouped Bar (Ward vs Type for User)
                user_ward_type_counts_qs = user_complaints.filter(
                    ward_number__isnull=False
                ).exclude(
                    ward_number__exact=''
                ).values(
                    'ward_number', 'complaint_type'
                ).annotate(count=Count('id')).order_by('ward_number', 'complaint_type')

                user_processed_ward_type = {}
                user_all_wards = set()
                user_all_types = set(complaint_types_dict.keys()) # Use all possible types

                for item in user_ward_type_counts_qs:
                    ward = item['ward_number']
                    if not ward: continue
                    ctype = item['complaint_type']
                    count = item['count']
                    if ward not in user_processed_ward_type:
                        user_processed_ward_type[ward] = {}
                    user_processed_ward_type[ward][ctype] = count
                    user_all_wards.add(ward)

                user_sorted_wards = sorted(list(user_all_wards), key=lambda w: int(w) if w.isdigit() else float('inf'))
                user_sorted_types = sorted(list(user_all_types))
                 # Consistent colors
                user_type_colors = { 'garbage': '#8B4513', 'pothole': '#9db17c', 'cattle': '#a6a6a6' }

                user_grouped_bar_datasets = []
                for ctype_key in user_sorted_types:
                    user_grouped_bar_datasets.append({
                        'label': complaint_types_dict.get(ctype_key, ctype_key.capitalize()),
                        'data': [user_processed_ward_type.get(ward, {}).get(ctype_key, 0) for ward in user_sorted_wards],
                        'backgroundColor': user_type_colors.get(ctype_key, '#6c757d')
                    })
                user_data['ward_type_grouped_bar'] = {
                    'labels': user_sorted_wards,
                    'datasets': user_grouped_bar_datasets
                }

                # User ART per Ward Bar Chart
                user_art_data = calculate_art_per_ward(user_complaints)
                user_data['art_per_ward'] = {
                    'labels': list(user_art_data.keys()),
                    'values': list(user_art_data.values())
                }

            except Exception as e:
                logger.error(f"Error calculating user-specific stats for {user.username}: {e}", exc_info=True)
            context['user_data'] = json.dumps(user_data) # Serialize user data

        # --- 2. Overall Statistics (Only for Guests) ---
        elif not is_authenticated: # Only calculate for guests
            overall_complaints = Complaint.objects.filter(
                is_trashed=False,
                is_permanently_deleted=False
            )
            overall_data = {}
            try:
                # Overall Type Doughnut
                overall_type_counts_qs = overall_complaints.values('complaint_type').annotate(count=Count('id')).order_by('complaint_type')
                overall_data['type_chart'] = {
                    'labels': [complaint_types_dict.get(item['complaint_type'], item['complaint_type'].capitalize()) for item in overall_type_counts_qs],
                    'values': [item['count'] for item in overall_type_counts_qs]
                }

                # Overall Status Doughnut
                overall_status_counts_qs = overall_complaints.values('status').annotate(count=Count('id')).order_by('status')
                overall_status_counts_sorted = sorted(overall_status_counts_qs, key=lambda x: status_order.get(x['status'], 99))
                overall_data['status_chart'] = {
                    'labels': [item['status'] for item in overall_status_counts_sorted],
                    'values': [item['count'] for item in overall_status_counts_sorted]
                }

                # Overall Grouped Bar (Ward vs Type) - Reuse logic from previous step if available
                overall_ward_type_counts_qs = overall_complaints.filter(
                    ward_number__isnull=False
                ).exclude(
                    ward_number__exact=''
                ).values(
                    'ward_number', 'complaint_type'
                ).annotate(count=Count('id')).order_by('ward_number', 'complaint_type')

                overall_processed_ward_type = {}
                overall_all_wards = set()
                overall_all_types = set(complaint_types_dict.keys())

                for item in overall_ward_type_counts_qs:
                    ward = item['ward_number']
                    if not ward: continue
                    ctype = item['complaint_type']
                    count = item['count']
                    if ward not in overall_processed_ward_type:
                        overall_processed_ward_type[ward] = {}
                    overall_processed_ward_type[ward][ctype] = count
                    overall_all_wards.add(ward)

                overall_sorted_wards = sorted(list(overall_all_wards), key=lambda w: int(w) if w.isdigit() else float('inf'))
                overall_sorted_types = sorted(list(overall_all_types))
                overall_type_colors = { 'garbage': '#8B4513', 'pothole': '#9db17c', 'cattle': '#a6a6a6' }

                overall_grouped_bar_datasets = []
                for ctype_key in overall_sorted_types:
                    overall_grouped_bar_datasets.append({
                        'label': complaint_types_dict.get(ctype_key, ctype_key.capitalize()),
                        'data': [overall_processed_ward_type.get(ward, {}).get(ctype_key, 0) for ward in overall_sorted_wards],
                        'backgroundColor': overall_type_colors.get(ctype_key, '#6c757d')
                    })
                overall_data['ward_type_grouped_bar'] = {
                    'labels': overall_sorted_wards,
                    'datasets': overall_grouped_bar_datasets
                }

                # Overall Heatmap Data Structure
                overall_data['heatmap'] = {
                    'wards': overall_sorted_wards,
                    'types': overall_sorted_types,
                    'type_names': complaint_types_dict,
                    'data': overall_processed_ward_type
                }

                # Overall Resolution Trend (Line Chart - Default 30 days)
                # NOTE: Dynamic timeframe handled by JS + API endpoint (created below)
                timespan = self.request.GET.get('timespan', 'month') # Default to month
                trend_data = calculate_trend_data(timespan, overall_complaints) # Use helper
                overall_data['resolution_trend'] = trend_data

                # Overall ART per Ward Bar Chart
                overall_art_data = calculate_art_per_ward(overall_complaints)
                overall_data['art_per_ward'] = {
                    'labels': list(overall_art_data.keys()),
                    'values': list(overall_art_data.values())
                }

            except Exception as e:
                logger.error(f"Error calculating overall stats for guest: {e}", exc_info=True)
            context['overall_data'] = json.dumps(overall_data) # Serialize overall data

        return context

# --- Helper for Trend Calculation ---
def calculate_trend_data(timespan, base_queryset):
    today = date.today()
    if timespan == 'year':
        start_date = today.replace(day=1, month=1) - timedelta(days=1) # End of prev year
        start_date = start_date.replace(day=1) # Start of first month of prev year? No, let's do last 12 months
        start_date = (today.replace(day=1) - timedelta(days=1)).replace(day=1) # Start of prev month
        start_date = start_date.replace(year=start_date.year -1 ) # Start of 12 months ago
        delta = timedelta(days=30) # Approximate month step
        num_periods = 12
        date_format = '%b %Y' # Month-Year format
        date_grouper = TruncDate('created_at', 'month', output_field=models.DateField())
        res_date_grouper = TruncDate('resolution_timestamp', 'month', output_field=models.DateField())

    elif timespan == 'week':
        start_date = today - timedelta(days=6)
        delta = timedelta(days=1)
        num_periods = 7
        date_format = '%a' # Day of week
        date_grouper = TruncDate('created_at')
        res_date_grouper = TruncDate('resolution_timestamp')
    else: # Default to month (last 30 days)
        start_date = today - timedelta(days=29)
        delta = timedelta(days=1)
        num_periods = 30
        date_format = '%b %d' # Month-Day format
        date_grouper = TruncDate('created_at')
        res_date_grouper = TruncDate('resolution_timestamp')


    date_range_objects = [start_date + timedelta(days=i) for i in range(num_periods)] if timespan != 'year' else [ (start_date.replace(day=1) + relativedelta(months=i)) for i in range(num_periods)]
    # Correct date range generation for 'year' might need python-dateutil: from dateutil.relativedelta import relativedelta
    # Simplified approach for year: Group by month directly in query if possible, or generate labels differently.
    # Let's stick to daily/weekly for now for simplicity or group monthly below.

    # For simplicity, we'll stick to daily for 'month' and 'week', and adjust label formatting
    if timespan == 'year': # Redo range generation for year (approx monthly labels)
       date_range_objects = [ (start_date + relativedelta(months=i)).replace(day=1) for i in range(num_periods)]
       date_labels = [d.strftime(date_format) for d in date_range_objects]
       date_grouper = TruncDate('created_at', 'month', output_field=models.DateField())
       res_date_grouper = TruncDate('resolution_timestamp', 'month', output_field=models.DateField())
    else:
        date_range_objects = [start_date + delta*i for i in range(num_periods)]
        date_labels = [d.strftime(date_format) for d in date_range_objects]


    # --- Created Counts ---
    created_counts_qs = base_queryset.filter(
        created_at__date__gte=start_date
    ).annotate(
        grouping_date=date_grouper
    ).values('grouping_date').annotate(count=Count('id')).order_by('grouping_date')
    created_counts_dict = {item['grouping_date']: item['count'] for item in created_counts_qs}

    # --- Resolved Counts ---
    resolved_updates = ComplaintUpdate.objects.filter(
        status='Resolved',
        updated_at__date__gte=start_date,
        complaint__in=base_queryset
    ).values('complaint_id').annotate(
        resolution_timestamp=Min('updated_at')
    ).filter(resolution_timestamp__isnull=False).annotate( # Ensure Min worked
         grouping_date=res_date_grouper
    )
    resolved_counts_qs = resolved_updates.values('grouping_date').annotate(
         count=Count('complaint_id', distinct=True) # Count distinct complaints resolved in the period
     ).order_by('grouping_date')
    resolved_counts_dict = {item['grouping_date']: item['count'] for item in resolved_counts_qs}

    # Map counts to the date range (handle potential type mismatch for year grouping)
    if timespan == 'year':
        # Match by year and month
        created_values = [created_counts_dict.get(d.replace(day=1), 0) for d in date_range_objects]
        resolved_values = [resolved_counts_dict.get(d.replace(day=1), 0) for d in date_range_objects]
    else:
        created_values = [created_counts_dict.get(d, 0) for d in date_range_objects]
        resolved_values = [resolved_counts_dict.get(d, 0) for d in date_range_objects]


    return {
        'labels': date_labels,
        'created_counts': created_values,
        'resolved_counts': resolved_values
    }

# --- API View for Trend Data ---
# Add this view function inside accounts/views.py
# You might need: from django.http import JsonResponse
# You might need: from django.db import models (if not already imported)
# You might need: from dateutil.relativedelta import relativedelta (install if needed: pip install python-dateutil)
from dateutil.relativedelta import relativedelta # Add this import

def get_overall_trend_data_api(request):
    """API endpoint to fetch overall trend data based on timespan."""
    timespan = request.GET.get('timespan', 'month') # week, month, year
    try:
        overall_complaints = Complaint.objects.filter(
            is_trashed=False,
            is_permanently_deleted=False
        )
        trend_data = calculate_trend_data(timespan, overall_complaints)
        return JsonResponse(trend_data)
    except Exception as e:
        logger.error(f"API Error fetching trend data (timespan: {timespan}): {e}", exc_info=True)
        return JsonResponse({'error': 'Could not fetch trend data'}, status=500)

class SignUpView(FormView):
    template_name = 'accounts/signup.html'
    form_class = SignUpForm
    # success_url = '/'  # Redirect to home page on success
    
    def dispatch(self, request, *args, **kwargs):
        # If user is already authenticated, log them out first
        if request.user.is_authenticated:
            logout(request)
            # Optional: Add a message to inform the user
            messages.info(request, 'You have been logged out to create a new account.')
            # Redirect back to signup page
            return redirect('signup')
        return super().dispatch(request, *args, **kwargs)
    
    def form_valid(self, form):
        # Don't save user immediately
        user = form.save(commit=False)
        
        # Format and store mobile number
        mobile_number = form.cleaned_data.get('mobile_number')
        formatted_number = f"+{settings.DEFAULT_COUNTRY_CODE}{mobile_number}" if not mobile_number.startswith('+') else mobile_number
        
        # Store data in session for verification
        self.request.session['user_signup_data'] = {
            'username': form.cleaned_data.get('username'),
            'email': form.cleaned_data.get('email'),
            'first_name': form.cleaned_data.get('first_name'),
            'last_name': form.cleaned_data.get('last_name'),
            'password': form.cleaned_data.get('password1'),
            'mobile_number': formatted_number,
        }
        
        # --- Wrap Twilio call in try...except ---
        try:
            status = send_verification_code(formatted_number)

            if status == 'pending':
                messages.success(self.request, 'Verification code sent to your mobile number.')
                return redirect('verify_phone') # Redirect to verification page
            else:
                # Handle cases where Twilio doesn't raise an exception but fails
                messages.error(self.request, f'Failed to send verification code. Status: {status}. Please try again.')
                return self.form_invalid(form) # Re-render signup form

        except TwilioRestException as e:
            logger.error(f"Twilio error sending verification to {formatted_number}: {e}", exc_info=True)

            # Create a user-friendly error message
            error_message = "Failed to send verification code. Please check the number and try again."
            # Specifically check for the unverified number error (code 21608)
            if e.code == 21608:
                error_message = ("Failed to send verification code. The phone number must be "
                                "verified in your Twilio trial account first.")
            elif e.code == 60200: # Example: Invalid parameter error
                error_message = "Failed to send verification code. The phone number format seems invalid."

            messages.error(self.request, error_message)
            return self.form_invalid(form) # Re-render signup form with the error message

        except Exception as e:
            # Catch any other unexpected errors during OTP sending
            logger.error(f"Unexpected error sending verification to {formatted_number}: {e}", exc_info=True)
            messages.error(self.request, 'An unexpected error occurred while trying to send the verification code. Please try again later.')
            return self.form_invalid(form)

    def form_invalid(self, form):
        messages.error(self.request, 'Please correct the errors below.')
        return super().form_invalid(form)

@method_decorator(login_required, name='dispatch')
class ProfileView(View):
    def get(self, request, *args, **kwargs):
        # Get all social accounts for current user
        social_accounts = SocialAccount.objects.filter(user=request.user)
        
        if hasattr(request.user, 'official_profile'):
            # Redirect government officials to their dashboard
            return redirect('authorities:authority_dashboard')
        else:
            # Normal users see their profile with complaint options and social accounts
            return render(request, 'accounts/profile.html', {
                'user': request.user,
                'social_accounts': social_accounts
            })

@method_decorator(login_required, name='dispatch')
class ProfileEditView(View):
    def get(self, request, *args, **kwargs):
        form = UserUpdateForm(instance=request.user)
        
        # Get or create profile for the user
        profile, created = UserProfile.objects.get_or_create(user=request.user)
        
        # Set initial mobile number from profile if it exists
        form.initial['mobile_number'] = profile.mobile_number
        
        password_form = PasswordChangeForm(user=request.user)
        return render(request, 'accounts/edit_profile.html', {
            'form': form,
            'password_form': password_form
        })
    
    def post(self, request, *args, **kwargs):
        action = request.POST.get('action')
        
        if action == 'update_profile':
            form = UserUpdateForm(request.POST, instance=request.user)
            password_form = PasswordChangeForm(user=request.user)
            
            if form.is_valid():
                user = form.save()
                
                # Get or create profile
                profile, created = UserProfile.objects.get_or_create(user=user)
                
                # Update the profile's mobile number
                profile.mobile_number = form.cleaned_data.get('mobile_number', '')
                profile.save()
                
                messages.success(request, 'Your profile has been updated successfully.')
                return redirect('profile')
                
        elif action == 'change_password':
            form = UserUpdateForm(instance=request.user)
            password_form = PasswordChangeForm(user=request.user, data=request.POST)
            
            if password_form.is_valid():
                password_form.save()
                # Update the session to prevent the user from being logged out
                update_session_auth_hash(request, request.user)
                messages.success(request, 'Your password has been changed successfully.')
                return redirect('profile')
        
        return render(request, 'accounts/edit_profile.html', {
            'form': form,
            'password_form': password_form
        })

@method_decorator(login_required, name='dispatch')
class DeleteProfileView(View):
    template_name = 'accounts/delete_profile.html'
    
    def get(self, request, *args, **kwargs):
        return render(request, self.template_name)
    
    def post(self, request, *args, **kwargs):
        try:
            # Soft delete user profile
            profile = request.user.profile
            profile.is_deleted = True
            profile.deleted_at = timezone.now()
            profile.save()
            
            # Soft delete user
            user = request.user
            user.is_active = False
            user.save()
            
            # Logout the user
            logout(request)
            
            messages.success(request, 'Your profile has been deactivated successfully.')
            return redirect('home')
        
        except Exception as e:
            messages.error(request, f'Error deleting profile: {str(e)}')
            return redirect('profile')

@method_decorator(login_required, name='dispatch')
class NavbarContextView(View):
    def get(self, request, *args, **kwargs):
        context = {}
        if hasattr(request.user, 'official_profile'):
            context['is_official'] = True
        else:
            context['is_official'] = False
        return context


@method_decorator(login_required, name='dispatch')
class HomeRedirectView(View):
    def get(self, request, *args, **kwargs):
        if hasattr(request.user, 'official_profile'):
            return redirect('authorities:authority_dashboard')
        return render(request, 'accounts/home.html', {'user': request.user})


class CustomLoginView(LoginView):
    template_name = 'accounts/login.html'
    
    def dispatch(self, request, *args, **kwargs):
        # If user is already authenticated, log them out first
        if request.user.is_authenticated:
            logout(request)
            messages.info(request, 'You have been logged out. Please login again.')
            return redirect('login')
        return super().dispatch(request, *args, **kwargs)
    
    def form_valid(self, form):
        # Call the parent class's form_valid method which will authenticate and login the user
        response = super().form_valid(form)
        
        # Explicitly manage session expiration
        if self.request.POST.get('remember_me') == 'on':
            # If "Remember me" is checked, use longer session
            self.request.session.set_expiry(settings.SESSION_COOKIE_AGE)
        else:
            # If not checked, session expires when browser closes
            self.request.session.set_expiry(0)
        
        return response


class LogoutView(View):
    def get(self, request, *args, **kwargs):
        logout(request)
        return redirect('login')

# email verification views

class UsernameOrEmailPasswordResetView(View):
    template_name = 'accounts/password_reset_form.html'
    form_class = UsernameOrEmailPasswordResetForm
    
    def get(self, request, *args, **kwargs):
        form = self.form_class()
        return render(request, self.template_name, {'form': form})
    
    def post(self, request, *args, **kwargs):
        form = self.form_class(request.POST)
        
        if form.is_valid():
            # This is critical - don't send emails yourself, use Django's built-in password reset
            # Django's PasswordResetForm handles sending emails properly
            opts = {
                'use_https': request.is_secure(),
                'token_generator': default_token_generator,
                'from_email': settings.DEFAULT_FROM_EMAIL,
                'subject_template_name': 'accounts/password_reset_subject.txt',
                'html_email_template_name': 'accounts/password_reset_email.html',
                'request': request,
            }
            # Let Django handle the email sending
            form.save(**opts)
            
            # Always redirect to success page
            return redirect('password_reset_done')
        
        return render(request, self.template_name, {'form': form})

class CustomPasswordResetDoneView(View):
    template_name = 'accounts/password_reset_done.html'
    
    def get(self, request, *args, **kwargs):
        return render(request, self.template_name)

class CustomPasswordResetConfirmView(PasswordResetConfirmView):
    template_name = 'accounts/password_reset_confirm.html'
    success_url = reverse_lazy('password_reset_complete')
    form_class = CustomSetPasswordForm

class CustomPasswordResetCompleteView(PasswordResetCompleteView):
    template_name = 'accounts/password_reset_complete.html'

class OTPVerificationView(View):
    template_name = 'accounts/verify_otp.html'
    
    def get(self, request, *args, **kwargs):
        if 'user_signup_data' not in request.session:
            messages.error(request, 'Session expired. Please sign up again.')
            return redirect('signup')
            
        form = OTPVerificationForm()
        return render(request, self.template_name, {'form': form})
    
    def post(self, request, *args, **kwargs):
        form = OTPVerificationForm(request.POST)
        
        if form.is_valid():
            user_data = request.session.get('user_signup_data', {})
            code = form.cleaned_data.get('code')
            
            if not user_data:
                messages.error(request, 'Session expired. Please sign up again.')
                return redirect('signup')
            
            status = check_verification_code(user_data['mobile_number'], code)
            
            if status == 'approved':
                # Create user
                user = User.objects.create_user(
                    username=user_data['username'],
                    email=user_data['email'],
                    first_name=user_data['first_name'],
                    last_name=user_data['last_name'],
                )
                user.set_password(user_data['password'])
                user.save()
                
                # Create profile with verified phone
                profile, created = UserProfile.objects.get_or_create(user=user)
                profile.mobile_number = user_data['mobile_number']
                profile.mobile_verified = True
                profile.save()
                
                # Clear session
                del request.session['user_signup_data']
                
                # Login the user
                login_user = authenticate(username=user_data['username'], password=user_data['password'])
                login(request, login_user, backend='django.contrib.auth.backends.ModelBackend')
                
                messages.success(request, 'Your account has been created successfully!')
                return redirect('home')
            else:
                messages.error(request, 'Invalid verification code. Please try again.')
        
        return render(request, self.template_name, {'form': form})

# Add mobile login views
class MobileLoginView(View):
    template_name = 'accounts/mobile_login.html'
    
    def get(self, request, *args, **kwargs):
        if request.user.is_authenticated:
            logout(request)
            
        form = MobileLoginForm()
        return render(request, self.template_name, {'form': form})
    
    def post(self, request, *args, **kwargs):
        form = MobileLoginForm(request.POST)
        
        if form.is_valid():
            mobile_number = form.cleaned_data.get('mobile_number')
            formatted_number = f"+{settings.DEFAULT_COUNTRY_CODE}{mobile_number}" if not mobile_number.startswith('+') else mobile_number
            
            # Check if a verified user exists with this number
            profile = UserProfile.objects.filter(mobile_number=formatted_number, mobile_verified=True).first()
            
            if profile:
                # Send OTP
                status = send_verification_code(formatted_number)
                
                # Store in session
                request.session['mobile_login'] = {
                    'mobile_number': formatted_number,
                    'user_id': profile.user.id
                }
                
                messages.success(request, 'Verification code sent to your mobile number.')
                return redirect('verify_login_otp')
            else:
                messages.error(request, 'No verified account found with this mobile number.')
        
        return render(request, self.template_name, {'form': form})

class VerifyOTPLoginView(View):
    template_name = 'accounts/verify_login_otp.html'
    
    def get(self, request, *args, **kwargs):
        if 'mobile_login' not in request.session:
            messages.error(request, 'Session expired. Please try again.')
            return redirect('mobile_login')
            
        form = OTPVerificationForm()
        return render(request, self.template_name, {'form': form})
    
    def post(self, request, *args, **kwargs):
        form = OTPVerificationForm(request.POST)
        
        if form.is_valid():
            login_data = request.session.get('mobile_login', {})
            code = form.cleaned_data.get('code')
            
            if not login_data:
                messages.error(request, 'Session expired. Please try again.')
                return redirect('mobile_login')
            
            status = check_verification_code(login_data['mobile_number'], code)
            
            if status == 'approved':
                # Get user and login
                try:
                    user = User.objects.get(id=login_data['user_id'])
                    
                    # Specify the backend when logging in
                    login(request, user, backend='django.contrib.auth.backends.ModelBackend')
                    
                    # Clear session
                    del request.session['mobile_login']
                    
                    messages.success(request, 'You have successfully logged in.')
                    return redirect('home')
                except User.DoesNotExist:
                    messages.error(request, 'User account no longer exists.')
                    return redirect('mobile_login')
            else:
                messages.error(request, 'Invalid verification code. Please try again.')
        
        return render(request, self.template_name, {'form': form})

def check_username(request):
    """Check if username is available."""
    username = request.GET.get('username', '')
    is_taken = User.objects.filter(username=username).exists()
    return JsonResponse({'is_taken': is_taken})

def check_email(request):
    """Check if email is registered."""
    email = request.GET.get('email', '')
    is_registered = User.objects.filter(email=email).exists()
    return JsonResponse({'is_registered': is_registered})

def check_mobile(request):
    """Check if mobile number is registered."""
    mobile = request.GET.get('mobile', '')
    
    # Format the mobile number for consistency
    if not mobile.startswith('+'):
        from django.conf import settings
        mobile = f"+{settings.DEFAULT_COUNTRY_CODE}{mobile}"
    
    is_registered = UserProfile.objects.filter(mobile_number=mobile).exists()
    return JsonResponse({'is_registered': is_registered})

logger = logging.getLogger(__name__)

class SocialMobileVerificationView(View):
    template_name = 'accounts/social_mobile_verification.html'
    form_class = SocialMobileVerificationForm
    
    def get(self, request, *args, **kwargs):
        # Check if there's pending social login data
        if 'pending_sociallogin' not in request.session:
            messages.error(request, 'No pending social login found.')
            return redirect('login')
        
        form = self.form_class()
        
        # Get information about the pending social login
        pending_data = request.session['pending_sociallogin']
        is_new = pending_data.get('is_new', False)
        
        context = {
            'form': form,
            'is_new': is_new,
        }
        
        if is_new:
            # For new user, show email and name
            user_data = pending_data.get('user_data', {})
            context['email'] = user_data.get('email', '')
            context['name'] = f"{user_data.get('first_name', '')} {user_data.get('last_name', '')}".strip()
        else:
            # For existing user, get user details
            user_id = pending_data.get('user_id')
            if user_id:
                try:
                    user = User.objects.get(id=user_id)
                    context['email'] = user.email
                    context['name'] = f"{user.first_name} {user.last_name}".strip() 
                except User.DoesNotExist:
                    pass
        
        return render(request, self.template_name, context)
    
    def post(self, request, *args, **kwargs):
        # Check if there's pending social login data
        if 'pending_sociallogin' not in request.session:
            messages.error(request, 'No pending social login found.')
            return redirect('login')
        
        form = self.form_class(request.POST)
        
        if form.is_valid():
            mobile_number = form.cleaned_data.get('mobile_number')
            formatted_number = f"+{settings.DEFAULT_COUNTRY_CODE}{mobile_number}" if not mobile_number.startswith('+') else mobile_number
            
            # Update session with mobile number
            request.session['pending_sociallogin']['mobile_number'] = formatted_number
            
            # Send verification code
            try:
                status = send_verification_code(formatted_number)
                
                if status == 'pending':
                    messages.success(request, 'Verification code sent to your mobile number.')
                    return redirect('verify_social_otp')
                else:
                    messages.error(request, f'Failed to send verification code. Status: {status}. Please try again.')
            except TwilioRestException as e:
                logger.error(f"Twilio error sending verification to {formatted_number}: {e}", exc_info=True)
                
                # Create a user-friendly error message
                error_message = "Failed to send verification code. Please check the number and try again."
                # Specifically check for the unverified number error (code 21608)
                if e.code == 21608:
                    error_message = ("Failed to send verification code. The phone number must be "
                                    "verified in your Twilio trial account first.")
                elif e.code == 60200:  # Example: Invalid parameter error
                    error_message = "Failed to send verification code. The phone number format seems invalid."
                
                messages.error(request, error_message)
            except Exception as e:
                logger.error(f"Unexpected error sending verification to {formatted_number}: {e}", exc_info=True)
                messages.error(request, 'An unexpected error occurred while trying to send the verification code. Please try again later.')
        
        # Get information about the pending social login
        pending_data = request.session['pending_sociallogin']
        is_new = pending_data.get('is_new', False)
        
        context = {
            'form': form,
            'is_new': is_new,
        }
        
        if is_new:
            # For new user, show email and name
            user_data = pending_data.get('user_data', {})
            context['email'] = user_data.get('email', '')
            context['name'] = f"{user_data.get('first_name', '')} {user_data.get('last_name', '')}".strip()
        else:
            # For existing user, get user details
            user_id = pending_data.get('user_id')
            if user_id:
                try:
                    user = User.objects.get(id=user_id)
                    context['email'] = user.email
                    context['name'] = f"{user.first_name} {user.last_name}".strip() 
                except User.DoesNotExist:
                    pass
                    
        return render(request, self.template_name, context)


class VerifySocialOTPView(View):
    template_name = 'accounts/verify_social_otp.html'
    form_class = OTPVerificationForm
    
    def get(self, request, *args, **kwargs):
        # Check if there's pending social login data
        if 'pending_sociallogin' not in request.session or 'mobile_number' not in request.session['pending_sociallogin']:
            messages.error(request, 'No pending verification found.')
            return redirect('login')
        
        form = self.form_class()
        return render(request, self.template_name, {'form': form})
    
    def post(self, request, *args, **kwargs):
        # Check if there's pending social login data
        if 'pending_sociallogin' not in request.session or 'mobile_number' not in request.session['pending_sociallogin']:
            messages.error(request, 'No pending verification found.')
            return redirect('login')
        
        form = self.form_class(request.POST)
        
        if form.is_valid():
            code = form.cleaned_data.get('code')
            pending_data = request.session['pending_sociallogin']
            mobile_number = pending_data.get('mobile_number')
            
            # Verify code
            status = check_verification_code(mobile_number, code)
            
            if status == 'approved':
                is_new = pending_data.get('is_new', False)
                
                if is_new:
                    # Create new user from social account data
                    user_data = pending_data.get('user_data', {})
                    
                    try:
                        # Create the user
                        user = User.objects.create_user(
                            username=user_data.get('username'),
                            email=user_data.get('email'),
                            first_name=user_data.get('first_name', ''),
                            last_name=user_data.get('last_name', ''),
                        )
                        
                        # Create profile with verified mobile number
                        profile, created = UserProfile.objects.get_or_create(user=user)
                        profile.mobile_number = mobile_number
                        profile.mobile_verified = True
                        profile.save()
                        
                        # Now that user is verified, need to create the social account connection
                        provider = user_data.get('provider')
                        
                        # Log the user in
                        login(request, user, backend='django.contrib.auth.backends.ModelBackend')
                        
                        # Redirect to create social account connection
                        messages.success(request, 'Your account has been created successfully! Please connect your social account again.')
                        return redirect('home')  # Redirect to home or to social account connection
                    
                    except Exception as e:
                        logger.error(f"Error creating user from social login: {e}", exc_info=True)
                        messages.error(request, 'Error creating your account. Please try again.')
                        return redirect('login')
                else:
                    # Existing user
                    user_id = pending_data.get('user_id')
                    
                    try:
                        user = User.objects.get(id=user_id)
                        
                        # Update profile with verified mobile number
                        profile, created = UserProfile.objects.get_or_create(user=user)
                        profile.mobile_number = mobile_number
                        profile.mobile_verified = True
                        profile.save()
                        
                        # Log the user in
                        login(request, user, backend='django.contrib.auth.backends.ModelBackend')
                        
                        messages.success(request, 'Mobile verification successful. Welcome back!')
                        return redirect('home')
                    
                    except User.DoesNotExist:
                        logger.error(f"User with id {user_id} not found during social verification")
                        messages.error(request, 'User account not found. Please try again.')
                        return redirect('login')
                
                # Clean up session
                if 'pending_sociallogin' in request.session:
                    del request.session['pending_sociallogin']
            else:
                messages.error(request, 'Invalid verification code. Please try again.')
        
        return render(request, self.template_name, {'form': form})