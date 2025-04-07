from django.urls import path
from . import views

urlpatterns = [
    path('', views.HomeView.as_view(), name='home'),
    path('signup/', views.SignUpView.as_view(), name='signup'),
    path('profile/', views.ProfileView.as_view(), name='profile'),
    path('profile/edit/', views.ProfileEditView.as_view(), name='edit_profile'),
    path('login/', views.CustomLoginView.as_view(), name='login'),
    path('logout/', views.LogoutView.as_view(), name='logout'),
    path('home/', views.HomeRedirectView.as_view(), name='home_view'),
    path('password-reset/', views.UsernameOrEmailPasswordResetView.as_view(), name='password_reset'),
    path('password-reset/done/', views.CustomPasswordResetDoneView.as_view(), name='password_reset_done'),
    path('password-reset-confirm/<uidb64>/<token>/', views.CustomPasswordResetConfirmView.as_view(),name='password_reset_confirm'),
    path('password-reset-complete/', views.CustomPasswordResetCompleteView.as_view(), name='password_reset_complete'),
    path('delete-profile/', views.DeleteProfileView.as_view(), name='delete_profile'),
    path('verify-phone/', views.OTPVerificationView.as_view(), name='verify_phone'),
    path('mobile-login/', views.MobileLoginView.as_view(), name='mobile_login'),
    path('verify-login-otp/', views.VerifyOTPLoginView.as_view(), name='verify_login_otp'),
    path('check-username/', views.check_username, name='check_username'),
    path('check-email/', views.check_email, name='check_email'),
    path('check-mobile/', views.check_mobile, name='check_mobile'),
    path('social-mobile-verification/', views.SocialMobileVerificationView.as_view(), name='social_mobile_verification'),
    path('verify-social-otp/', views.VerifySocialOTPView.as_view(), name='verify_social_otp'),
    path('api/overall-trend/', views.get_overall_trend_data_api, name='api_overall_trend_data'),
]