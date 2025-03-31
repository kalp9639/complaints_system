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
from .forms import SignUpForm, UserUpdateForm, PasswordChangeForm, UsernameOrEmailPasswordResetForm, CustomSetPasswordForm
from .models import UserProfile

from django.conf import settings 
from django.contrib.auth.tokens import default_token_generator
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode
from django.utils.html import strip_tags
from django.core.mail import EmailMultiAlternatives

class HomeView(TemplateView):
    template_name = 'accounts/home.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        if self.request.user.is_authenticated and hasattr(self.request.user, 'official_profile'):
            context['is_official'] = True
        else:
            context['is_official'] = False
        return context


class SignUpView(FormView):
    template_name = 'accounts/signup.html'
    form_class = SignUpForm
    success_url = '/'  # Redirect to home page on success
    
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
        user = form.save()
        
        # Set the mobile number in the user profile if provided
        mobile_number = form.cleaned_data.get('mobile_number')
        if mobile_number:
            profile, created = UserProfile.objects.get_or_create(user=user)
            profile.mobile_number = mobile_number
            profile.save()
        
        username = form.cleaned_data.get('username')
        raw_password = form.cleaned_data.get('password1')
        user = authenticate(username=username, password=raw_password)
        login(self.request, user)
        messages.success(self.request, f'Account created for {username}! You are now logged in.')
        return super().form_valid(form)
    
    def form_invalid(self, form):
        messages.error(self.request, 'Please correct the errors below.')
        return super().form_invalid(form)


# Modify ProfileView to just show profile info
@method_decorator(login_required, name='dispatch')
class ProfileView(View):
    def get(self, request, *args, **kwargs):
        if hasattr(request.user, 'official_profile'):
            # Redirect government officials to their dashboard
            return redirect('authorities:authority_dashboard')
        else:
            # Normal users see their profile with complaint options
            return render(request, 'accounts/profile.html', {'user': request.user})

# Add a new view for profile editing
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

# Replace your UsernameOrEmailPasswordResetView with this version

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