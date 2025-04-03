from allauth.account.adapter import DefaultAccountAdapter
from allauth.socialaccount.adapter import DefaultSocialAccountAdapter
from allauth.exceptions import ImmediateHttpResponse
from django.contrib.auth.models import User
from django.shortcuts import redirect
from django.contrib import messages
from .models import UserProfile
from django.urls import reverse

class CustomSocialAccountAdapter(DefaultSocialAccountAdapter):
    """
    Custom adapter to link social accounts to existing user accounts with matching email
    and require mobile verification for new social sign-ups
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
                # Check if user has a verified mobile number
                try:
                    profile = UserProfile.objects.get(user=user)
                    if not profile.mobile_verified:
                        # Store the social login data in the session
                        request.session['pending_sociallogin'] = {
                            'email': email,
                            'provider': sociallogin.account.provider,
                            'user_id': user.id,
                            'is_new': False
                        }
                        # Redirect to mobile verification
                        raise ImmediateHttpResponse(redirect('social_mobile_verification'))
                except UserProfile.DoesNotExist:
                    # No profile exists, create one and redirect to verification
                    request.session['pending_sociallogin'] = {
                        'email': email,
                        'provider': sociallogin.account.provider,
                        'user_id': user.id,
                        'is_new': False
                    }
                    raise ImmediateHttpResponse(redirect('social_mobile_verification'))
                
                return
                
            # If social account exists but connected to another user, handle the conflict
            if sociallogin.user != user:
                # Connect this social account to the existing user
                sociallogin.connect(request, user)
                
                # Check if user has a verified mobile number
                try:
                    profile = UserProfile.objects.get(user=user)
                    if not profile.mobile_verified:
                        # Store the social login data in the session
                        request.session['pending_sociallogin'] = {
                            'email': email,
                            'provider': sociallogin.account.provider,
                            'user_id': user.id,
                            'is_new': False
                        }
                        # Redirect to mobile verification
                        raise ImmediateHttpResponse(redirect('social_mobile_verification'))
                except UserProfile.DoesNotExist:
                    # No profile exists, create one and redirect to verification
                    request.session['pending_sociallogin'] = {
                        'email': email,
                        'provider': sociallogin.account.provider,
                        'user_id': user.id,
                        'is_new': False
                    }
                    raise ImmediateHttpResponse(redirect('social_mobile_verification'))
                
                # Add a success message
                messages.success(
                    request, 
                    f"Your Google account has been connected to your existing account with email {email}."
                )
                
        except User.DoesNotExist:
            # New user - Store the social login data in the session
            # First extract the user information from sociallogin
            user_data = {
                'email': email,
                'username': sociallogin.account.extra_data.get('email').split('@')[0],  # Default username from email
                'first_name': sociallogin.account.extra_data.get('given_name', ''),
                'last_name': sociallogin.account.extra_data.get('family_name', ''),
                'provider': sociallogin.account.provider
            }
            
            request.session['pending_sociallogin'] = {
                'user_data': user_data,
                'is_new': True
            }
            
            # Interrupt the social login process and redirect to mobile verification
            raise ImmediateHttpResponse(redirect('social_mobile_verification'))