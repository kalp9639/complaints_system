from allauth.account.adapter import DefaultAccountAdapter
from allauth.socialaccount.adapter import DefaultSocialAccountAdapter
from allauth.exceptions import ImmediateHttpResponse
from django.contrib.auth.models import User
from django.shortcuts import redirect
from django.contrib import messages

class CustomSocialAccountAdapter(DefaultSocialAccountAdapter):
    """
    Custom adapter to link social accounts to existing user accounts with matching email
    """
    def pre_social_login(self, request, sociallogin):
        """
        Called before the social login process starts.
        """
        # Get email from social account
        email = sociallogin.account.extra_data.get('email', '')
        if not email:
            return

        # Check if a user exists with this email
        try:
            user = User.objects.get(email=email)
            
            # If this social account is already connected to the user, continue as normal
            if sociallogin.is_existing:
                return
                
            # If social account exists but connected to another user, handle the conflict
            if sociallogin.user != user:
                # Connect this social account to the existing user
                sociallogin.connect(request, user)
                
                # Add a success message
                messages.success(
                    request, 
                    f"Your Google account has been connected to your existing account with email {email}."
                )
                
        except User.DoesNotExist:
            # No matching user, allauth will create a new user account
            pass