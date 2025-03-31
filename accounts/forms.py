# accounts/forms.py

from django import forms
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm, PasswordResetForm, SetPasswordForm
from django.contrib.auth.models import User
from django.contrib.auth.forms import PasswordResetForm
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.contrib.auth.tokens import default_token_generator

class SignUpForm(UserCreationForm):
    email = forms.EmailField(max_length=254, required=True, help_text='Required. Enter a valid email address.')
    first_name = forms.CharField(max_length=30, required=True, help_text='Required.')
    last_name = forms.CharField(max_length=30, required=True, help_text='Required.')
    mobile_number = forms.CharField(max_length=15, required=False, help_text='Required. Enter a valid mobile number.')
    
    class Meta:
        model = User
        fields = ('username', 'first_name', 'last_name', 'email', 'mobile_number', 'password1', 'password2')

class UserUpdateForm(forms.ModelForm):
    email = forms.EmailField(max_length=254, required=True, help_text='Required. Enter a valid email address.')
    first_name = forms.CharField(max_length=30, required=True, help_text='Required.')
    last_name = forms.CharField(max_length=30, required=True, help_text='Required.')
    username = forms.CharField(max_length=150, required=True)
    mobile_number = forms.CharField(max_length=15, required=False, help_text='Required. Enter a valid mobile number.')
    
    class Meta:
        model = User
        fields = ('username', 'first_name', 'last_name', 'email', 'mobile_number')
                
    def clean_username(self):
        username = self.cleaned_data.get('username')
        # Check if username is being changed
        if username != self.instance.username:
            # Check if new username already exists
            if User.objects.filter(username=username).exists():
                raise forms.ValidationError('A user with that username already exists.')
        return username

class PasswordChangeForm(forms.Form):
    old_password = forms.CharField(widget=forms.PasswordInput(), label="Current Password")
    new_password1 = forms.CharField(widget=forms.PasswordInput(), label="New Password")
    new_password2 = forms.CharField(widget=forms.PasswordInput(), label="Confirm New Password")
    
    def __init__(self, user, *args, **kwargs):
        self.user = user
        super().__init__(*args, **kwargs)
    
    def clean_old_password(self):
        old_password = self.cleaned_data.get('old_password')
        if not self.user.check_password(old_password):
            raise forms.ValidationError('Your current password is incorrect.')
        return old_password
    
    def clean(self):
        cleaned_data = super().clean()
        password1 = cleaned_data.get('new_password1')
        password2 = cleaned_data.get('new_password2')
        
        if password1 and password2:
            if password1 != password2:
                raise forms.ValidationError('The two password fields didn\'t match.')
        return cleaned_data
    
    def save(self, commit=True):
        self.user.set_password(self.cleaned_data['new_password1'])
        if commit:
            self.user.save()
        return self.user

class UsernameOrEmailPasswordResetForm(PasswordResetForm):
    def clean_email(self):
        User = get_user_model()
        email = self.cleaned_data['email']
        
        # Check if the user exists with this email
        if not User.objects.filter(email__iexact=email, is_active=True).exists():
            # Don't raise an error - silently accept non-existent emails
            # This is for security to prevent user enumeration
            pass
            
        return email
        
    def save(self, domain_override=None, subject_template_name='registration/password_reset_subject.txt',
             email_template_name='registration/password_reset_email.html',
             use_https=False, token_generator=default_token_generator,
             from_email=None, request=None, html_email_template_name=None,
             extra_email_context=None):
        """
        Generate a one-use only link for resetting password and send it to the
        user. This overrides the parent method to properly handle non-existent
        emails silently.
        """
        email = self.cleaned_data["email"]
        User = get_user_model()
        
        # Check if active users exist with this email
        active_users = User.objects.filter(email__iexact=email, is_active=True)
        
        if active_users.exists():
            # Only proceed with email sending if users actually exist
            for user in active_users:
                # Store the found user for reference
                self.user_cache = user
                # Let the parent class handle the actual email sending
                super().save(
                    domain_override, subject_template_name, email_template_name,
                    use_https, token_generator, from_email, request,
                    html_email_template_name, extra_email_context
                )

class CustomSetPasswordForm(SetPasswordForm):
    """
    Custom form for setting a new password
    """
    new_password1 = forms.CharField(
        label="New password",
        widget=forms.PasswordInput(attrs={'class': 'form-control'}),
        strip=False,
    )
    new_password2 = forms.CharField(
        label="Confirm new password",
        strip=False,
        widget=forms.PasswordInput(attrs={'class': 'form-control'}),
    )