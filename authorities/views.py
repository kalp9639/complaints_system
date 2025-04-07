# authorities/views.py

# Django Shortcuts
from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse
from django.http import Http404, JsonResponse 

# Authentication & Authorization
from django.contrib.auth import login, authenticate, logout, update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.contrib.auth.forms import PasswordChangeForm

# Django Views
from django.views import View
from django.views.generic import FormView, TemplateView, ListView, DetailView, UpdateView

# Django Utilities & Security
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_protect
from django.contrib import messages
from django.utils import timezone

# Forms & Models
from .forms import OfficialSignUpForm, ComplaintUpdateForm, OfficialProfileUpdateForm
from complaints.models import Complaint
from .models import GovernmentOfficial, ComplaintUpdate

# --- QR Verification View ---
from django.conf import settings
from django.http import JsonResponse
from pyzbar.pyzbar import decode
from PIL import Image
import os

# Import ART calculation function from accounts.views
from accounts.views import calculate_art_per_ward

# Standard Library
import json
import logging # Import logging

logger = logging.getLogger(__name__) # Get logger instance

@method_decorator(csrf_protect, name='dispatch')
class OfficialSignUpView(FormView):
    template_name = 'authorities/official_signup.html'
    form_class = OfficialSignUpForm
    success_url = '/authorities/dashboard/'

    def dispatch(self, request, *args, **kwargs):
        # Check if the QR code has been verified
        if not request.session.get('authority_qr_verified', False):
            messages.error(request, 'Unauthorized Access: Please scan the authorized QR code first.')
            return redirect('authorities:qr_verification')
        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        try:
            user = form.save()
            username = form.cleaned_data.get('username')
            raw_password = form.cleaned_data.get('password1')
            user = authenticate(username=username, password=raw_password)
            if user: # Check if authentication succeeded
                login(self.request, user)
                 # Clear the verification flag from the session after successful signup
                if 'authority_qr_verified' in self.request.session:
                    del self.request.session['authority_qr_verified']
                messages.success(self.request, f'Official account created for {username}!')
                return super().form_valid(form)
            else:
                 messages.error(self.request, 'Account created, but automatic login failed. Please login manually.')
                 return redirect('authorities:official_login')

        except Exception as e:
            logger.error(f"Error during official signup for {form.cleaned_data.get('username')}: {e}", exc_info=True) # Log detailed error
            messages.error(self.request, f'Error creating account: {str(e)}')
            return self.form_invalid(form)

class OfficialLoginView(View):
    template_name = 'authorities/official_login.html'

    def get(self, request, *args, **kwargs):
        # If already logged in as an official, redirect to dashboard
        if request.user.is_authenticated and hasattr(request.user, 'official_profile'):
            return redirect('authorities:authority_dashboard')
        # If logged in but not official, maybe logout first or show message?
        elif request.user.is_authenticated:
            logout(request)
            messages.info(request, 'You have been logged out. Please login with official credentials.')
        return render(request, self.template_name)

    def post(self, request, *args, **kwargs):
        username = request.POST.get('username') # Use .get for safety
        password = request.POST.get('password')

        if not username or not password:
             messages.error(request, 'Please provide both username and password.')
             return render(request, self.template_name)

        user = authenticate(request, username=username, password=password)

        if user is not None:
            try:
                # Check if the authenticated user IS an official
                official = user.official_profile
                login(request, user)
                messages.success(request, f'Welcome, {user.get_full_name()}!')
                return redirect('authorities:authority_dashboard')
            except GovernmentOfficial.DoesNotExist:
                # User exists but is NOT an official
                messages.error(request, 'Invalid credentials or not registered as an official.')
        else:
            # Authentication failed (wrong username/password)
            messages.error(request, 'Invalid username or password.')

        return render(request, self.template_name)


class OfficialLogoutView(View):
    def get(self, request, *args, **kwargs):
        logout(request)
        messages.success(request, 'You have been successfully logged out.') # Add success message
        return redirect('authorities:official_login')


@method_decorator(login_required, name='dispatch')
class AuthorityDashboardView(TemplateView):
    template_name = 'authorities/authority_dashboard.html'

    def dispatch(self, request, *args, **kwargs):
        # Ensure user is logged in and is an official
        if not request.user.is_authenticated:
             return redirect('authorities:official_login')
        try:
            self.official = request.user.official_profile
            return super().dispatch(request, *args, **kwargs)
        except GovernmentOfficial.DoesNotExist:
            # If logged-in user is not an official, redirect them appropriately
            messages.error(request, 'Access denied. You are not registered as a government official.')
            # Logout and redirect to official login, or redirect to citizen home
            logout(request) # Log out the non-official user
            return redirect('authorities:official_login')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        # Get all non-deleted complaints for the official's ward
        complaints = Complaint.objects.filter(
            ward_number=self.official.ward_number,
            is_trashed=False,
            is_permanently_deleted=False
        )

        total_count = complaints.count()
        resolved_count = complaints.filter(status='Resolved').count()

        # --- Calculate Resolution Rate ---
        resolution_rate = (resolved_count / total_count * 100) if total_count > 0 else 0

        # --- Calculate Average Resolution Time (ART) for this specific ward ---
        ward_art_data = calculate_art_per_ward(complaints) # Use the helper
        average_resolution_time = ward_art_data.get(self.official.ward_number, None) # Get ART for this ward

        # --- Get 5 Oldest Pending/In Progress Complaints ---
        oldest_pending_complaints = complaints.filter(
            status__in=['Pending', 'In Progress']
        ).order_by('created_at')[:5]

        context.update({
            'official': self.official,
            'total_complaints': total_count,
            'pending_complaints': complaints.filter(status='Pending').count(),
            'in_progress_complaints': complaints.filter(status='In Progress').count(),
            'resolved_complaints': resolved_count,
            'resolution_rate': resolution_rate, # Add to context
            'average_resolution_time': average_resolution_time, # Add to context
            'oldest_pending_complaints': oldest_pending_complaints, # Add to context
        })
        return context


@method_decorator(login_required, name='dispatch')
class AuthorityComplaintsListView(ListView):
    template_name = 'authorities/authority_complaints_list.html'
    context_object_name = 'complaints'
    paginate_by = 15 # Optional: Add pagination

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('authorities:official_login')
        try:
            self.official = request.user.official_profile
            return super().dispatch(request, *args, **kwargs)
        except GovernmentOfficial.DoesNotExist:
            messages.error(request, 'Access denied. You are not registered as a government official.')
            logout(request)
            return redirect('authorities:official_login')

    def get_queryset(self):
        # Start with non-deleted complaints for the ward
        queryset = Complaint.objects.filter(
            ward_number=self.official.ward_number,
            is_trashed=False,
            is_permanently_deleted=False
        )

        # Get filter parameters
        complaint_type = self.request.GET.get('type')
        status = self.request.GET.get('status')
        sort = self.request.GET.get('sort', 'newest')

        # Apply filters if present
        if complaint_type:
            queryset = queryset.filter(complaint_type=complaint_type)
        if status:
            queryset = queryset.filter(status=status)

        # Apply sorting
        if sort == 'oldest':
            queryset = queryset.order_by('created_at')
        else:  # default to newest
            queryset = queryset.order_by('-created_at')

        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        # Add complaint types
        context['complaint_types'] = Complaint.COMPLAINT_TYPES

        # Get selected filters for template
        context['selected_type'] = self.request.GET.get('type')
        context['selected_status'] = self.request.GET.get('status')
        context['selected_sort'] = self.request.GET.get('sort', 'newest')

        # Add query parameters for pagination links
        query_params = self.request.GET.copy()
        if 'page' in query_params:
            del query_params['page']
        context['query_params'] = query_params.urlencode()


        return context


@method_decorator(login_required, name='dispatch')
class AuthorityComplaintsMapView(View):
    template_name = 'authorities/authority_complaints_map.html'

    def dispatch(self, request, *args, **kwargs):
        # ... (dispatch logic remains the same) ...
        if not request.user.is_authenticated:
            return redirect('authorities:official_login')
        try:
            self.official = request.user.official_profile
            return super().dispatch(request, *args, **kwargs)
        except GovernmentOfficial.DoesNotExist:
            messages.error(request, 'Access denied. You are not registered as a government official.')
            logout(request)
            return redirect('authorities:official_login')

    def get(self, request, *args, **kwargs):
        # ... (filtering logic remains the same) ...
        complaints = Complaint.objects.filter(
            ward_number=self.official.ward_number,
            is_trashed=False,
            is_permanently_deleted=False,
            latitude__isnull=False, # Ensure coordinates exist
            longitude__isnull=False
        )
        complaint_type = request.GET.get('type')
        status = request.GET.get('status')
        sort = request.GET.get('sort', 'newest')
        if complaint_type:
            complaints = complaints.filter(complaint_type=complaint_type)
        if status:
            complaints = complaints.filter(status=status)
        if sort == 'oldest':
            complaints = complaints.order_by('created_at')
        else:
            complaints = complaints.order_by('-created_at')

        # Prepare complaints data for map
        complaints_data = []
        for complaint in complaints:
            complaints_data.append({
                'id': complaint.id,
                'lat': float(complaint.latitude),
                'lng': float(complaint.longitude),
                'type': complaint.get_complaint_type_display(),
                'status': complaint.status,
                # Uses the now imported 'reverse' function correctly
                'url': reverse('authorities:complaint_detail', kwargs={'pk': complaint.id}),
                'ward': complaint.ward_number or 'Unknown',
                'submitted_by': complaint.user.get_full_name() or complaint.user.username,
                'date': complaint.created_at.strftime('%Y-%m-%d %H:%M'),
                'image_url': complaint.image.url if complaint.image else None,
            })

        context = {
            'complaints_data': json.dumps(complaints_data),
            'complaint_count': len(complaints_data),
            'selected_type': complaint_type,
            'selected_status': status,
            'selected_sort': sort,
            'complaint_types': Complaint.COMPLAINT_TYPES,
            'official': self.official,
        }
        return render(request, self.template_name, context)

@method_decorator(login_required, name='dispatch')
class UpdateComplaintStatusView(View):
    template_name = 'authorities/update_complaint_status.html'

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
             return redirect('authorities:official_login')
        try:
            self.official = request.user.official_profile
            self.complaint = get_object_or_404(
                Complaint,
                id=kwargs.get('complaint_id'),
                ward_number=self.official.ward_number, # Ensure official can only update their ward's complaints
                is_trashed=False, # Cannot update trashed complaints
                is_permanently_deleted=False
            )
            return super().dispatch(request, *args, **kwargs)
        except GovernmentOfficial.DoesNotExist:
            messages.error(request, 'Access denied. You are not registered as a government official.')
            logout(request)
            return redirect('authorities:official_login')
        except Http404:
             messages.error(request, 'Complaint not found or you do not have permission to update it.')
             return redirect('authorities:authority_complaints_list')


    def get(self, request, *args, **kwargs):
        form = ComplaintUpdateForm(initial={'status': self.complaint.status})
        return render(request, self.template_name, {
            'form': form,
            'complaint': self.complaint
        })

    def post(self, request, *args, **kwargs):
        form = ComplaintUpdateForm(request.POST, request.FILES)
        if form.is_valid():
            # Don't save the update immediately
            update = form.save(commit=False)
            update.complaint = self.complaint
            update.official = self.official
            
            # Get the new status from the form
            new_status = form.cleaned_data['status']

            # Check if the status actually changed
            if new_status != self.complaint.status:
                # Save the ComplaintUpdate record FIRST
                update.save()
                # THEN update the Complaint status
                self.complaint.status = new_status
                self.complaint.save(update_fields=['status']) # Optimize save
                messages.success(request, f'Complaint #{self.complaint.id} status updated to "{new_status}" successfully!')
                # Redirect to the detail view of the updated complaint
                return redirect('authorities:complaint_detail', pk=self.complaint.id)
            else:
                 # Status didn't change, but maybe description/image was added?
                 # Still save the update record if image or description exists
                 if update.update_description or update.proof_image:
                     update.save()
                     messages.info(request, f'Note added/Proof uploaded for Complaint #{self.complaint.id}. Status remains "{self.complaint.status}".')
                     return redirect('authorities:complaint_detail', pk=self.complaint.id)
                 else:
                     # No changes made
                     messages.warning(request, 'No changes detected in status, description, or proof image.')
                     # Redirect back to the update form or detail view
                     return redirect('authorities:update_complaint_status', complaint_id=self.complaint.id)


        # If form is invalid, re-render the page with errors
        return render(request, self.template_name, {
            'form': form,
            'complaint': self.complaint
        })

@method_decorator(login_required, name='dispatch')
class ComplaintDetailView(DetailView):
    model = Complaint
    template_name = 'complaints/complaint_detail.html' # Using the complaints app template
    context_object_name = 'complaint'

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('authorities:official_login')
        try:
            # Ensure the logged-in user is an official
            self.official = request.user.official_profile

            # Get the complaint object
            complaint = self.get_object()

            # Check if the complaint is deleted
            if complaint.is_trashed or complaint.is_permanently_deleted:
                 messages.error(request, 'This complaint is no longer available.')
                 return redirect('authorities:authority_complaints_list')


            # Check if this official is authorized to view this complaint (matches ward)
            if complaint.ward_number != self.official.ward_number:
                messages.error(request, 'You do not have permission to view this complaint.')
                # Redirect to their own list view, not home
                return redirect('authorities:authority_complaints_list')

            return super().dispatch(request, *args, **kwargs)

        except GovernmentOfficial.DoesNotExist:
            messages.error(request, 'Access denied. You are not registered as a government official.')
            logout(request)
            return redirect('authorities:official_login')
        except Http404:
             messages.error(request, 'Complaint not found.')
             return redirect('authorities:authority_complaints_list')


    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        complaint = self.get_object() # Complaint is already fetched

        # Add is_official flag and ordered updates
        context.update({
            'is_official': True, # We know this user is an official if they reached here
            'updates': complaint.updates.order_by('-updated_at').select_related('official__user') # Optimize
        })

        return context

@method_decorator(login_required, name='dispatch')
class OfficialProfileUpdateView(View):
    template_name = 'authorities/official_profile_edit.html'

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('authorities:official_login')
        try:
            self.official = request.user.official_profile
            return super().dispatch(request, *args, **kwargs)
        except GovernmentOfficial.DoesNotExist:
            messages.error(request, 'Access denied. You are not registered as a government official.')
            logout(request)
            return redirect('authorities:official_login')

    def get(self, request, *args, **kwargs):
        form = OfficialProfileUpdateForm(instance=self.official, user=request.user)
        password_form = PasswordChangeForm(user=request.user) # Include password form
        # Add Bootstrap classes to password form fields dynamically
        for field in password_form.fields.values():
             field.widget.attrs.update({'class': 'form-control'})
        return render(request, self.template_name, {'form': form, 'password_form': password_form})

    def post(self, request, *args, **kwargs):
        action = request.POST.get('action') # Check which form was submitted

        # Initialize forms for re-rendering if needed
        form = OfficialProfileUpdateForm(instance=self.official, user=request.user)
        password_form = PasswordChangeForm(user=request.user)
        # Add Bootstrap classes to password form fields dynamically
        for field in password_form.fields.values():
            field.widget.attrs.update({'class': 'form-control'})

        if action == 'update_profile':
            form = OfficialProfileUpdateForm(request.POST, instance=self.official, user=request.user)
            if form.is_valid():
                # Update User model fields
                user = request.user
                user.username = form.cleaned_data['username']
                user.first_name = form.cleaned_data['first_name']
                user.last_name = form.cleaned_data['last_name']
                user.email = form.cleaned_data['email']
                user.save()

                # Save GovernmentOfficial model fields
                official = form.save(commit=False)
                official.user = user # Ensure user association is correct
                official.save()

                messages.success(request, 'Your profile was successfully updated!')
                return redirect('authorities:authority_dashboard')
            # If form invalid, fall through to render with errors

        elif action == 'change_password':
            password_form = PasswordChangeForm(user=request.user, data=request.POST)
            # Re-add Bootstrap classes if form is re-rendered
            for field in password_form.fields.values():
                 field.widget.attrs.update({'class': 'form-control'})
            if password_form.is_valid():
                user = password_form.save()
                # Update session to prevent logging out
                update_session_auth_hash(request, user)
                messages.success(request, 'Your password was successfully updated!')
                return redirect('authorities:edit_profile') # Redirect back to edit page
            # If form invalid, fall through to render with errors

        # Render the template with potentially invalid forms
        return render(request, self.template_name, {'form': form, 'password_form': password_form})

@method_decorator(login_required, name='dispatch')
class OfficialDeleteProfileView(View):
    template_name = 'authorities/delete_profile.html'

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
             return redirect('authorities:official_login')
        try:
            self.official = request.user.official_profile
            return super().dispatch(request, *args, **kwargs)
        except GovernmentOfficial.DoesNotExist:
            messages.error(request, 'Access denied. You are not registered as a government official.')
            # Redirect non-officials away
            return redirect('home') # Or logout?

    def get(self, request, *args, **kwargs):
        return render(request, self.template_name)

    def post(self, request, *args, **kwargs):
        try:
            # Soft delete official profile
            official = self.official
            official.is_deleted = True
            official.deleted_at = timezone.now()
            official.save()

            # Soft delete user
            user = request.user
            user.is_active = False
            user.save()

            # Logout the user
            logout(request)

            messages.success(request, 'Your official profile has been deactivated successfully.')
            return redirect('home') # Redirect to main home page after deactivation

        except Exception as e:
            logger.error(f"Error deleting official profile for user {request.user.username}: {e}", exc_info=True)
            messages.error(request, f'Error deleting profile: {str(e)}')
            return redirect('authorities:authority_dashboard')

class AuthorityQRVerificationView(View):
    template_name = 'authorities/qr_verification.html'

    def get(self, request, *args, **kwargs):
         # If user is already logged in, don't show QR page
         if request.user.is_authenticated:
             # If official, go to dashboard, otherwise home
             if hasattr(request.user, 'official_profile'):
                 return redirect('authorities:authority_dashboard')
             else:
                 return redirect('home')
         # If QR already verified in session, redirect to signup
         if request.session.get('authority_qr_verified', False):
             return redirect('authorities:official_signup')
         return render(request, self.template_name)

    def post(self, request, *args, **kwargs):
        if 'qr_image' not in request.FILES:
            return JsonResponse({'success': False, 'message': 'No image file provided'})

        try:
            # Get the uploaded image
            image_file = request.FILES['qr_image']

            # Open the image with PIL - handle potential errors
            try:
                image = Image.open(image_file)
                # Attempt to convert to RGB if it's not, as pyzbar might prefer it
                if image.mode != 'RGB':
                     image = image.convert('RGB')
            except Exception as img_err:
                 logger.error(f"Error opening image file: {img_err}", exc_info=True)
                 return JsonResponse({'success': False, 'message': 'Invalid or corrupted image file.'})


            # Decode the QR code
            decoded_objects = decode(image)

            if not decoded_objects:
                 logger.warning("No QR code found in the uploaded image.")
                 return JsonResponse({'success': False, 'message': 'No QR code found in the image. Please upload a clear image.'})

            # Get the QR code data (use first found QR code)
            qr_data = decoded_objects[0].data.decode('utf-8')

            # Print for debugging (consider removing in production)
            logger.debug(f"Decoded QR Code Content: {qr_data}")
            # logger.debug(f"Expected Secret: {settings.AUTHORITY_QR_SECRET_KEY}")

            # Compare with the secret key
            if qr_data == settings.AUTHORITY_QR_SECRET_KEY:
                # Set session flag
                request.session['authority_qr_verified'] = True
                request.session.save() # Ensure session is saved
                logger.info("Authority QR code verified successfully.")
                # Return redirect URL for JS
                return JsonResponse({'success': True, 'redirect': reverse('authorities:official_signup')})
            else:
                logger.warning(f"Invalid QR code data received: {qr_data}")
                return JsonResponse({'success': False, 'message': 'Invalid QR code. Unauthorized access.'})

        except Exception as e:
            logger.error(f"Error processing QR code: {str(e)}", exc_info=True)
            return JsonResponse({'success': False, 'message': f'Error processing QR code: {str(e)}'})