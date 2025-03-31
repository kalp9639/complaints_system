from django.urls import path
from . import views

app_name = 'authorities'

urlpatterns = [
    path('signup/', views.OfficialSignUpView.as_view(), name='official_signup'),
    path('login/', views.OfficialLoginView.as_view(), name='official_login'),
    path('logout/', views.OfficialLogoutView.as_view(), name='official_logout'),
    path('dashboard/', views.AuthorityDashboardView.as_view(), name='authority_dashboard'),
    path('complaints/', views.AuthorityComplaintsListView.as_view(), name='authority_complaints_list'),
    path('complaints/map/', views.AuthorityComplaintsMapView.as_view(), name='authority_complaints_map'),
    path('complaint/<int:complaint_id>/update/', views.UpdateComplaintStatusView.as_view(), name='update_complaint_status'),
    path('complaints/view/', views.OfficialComplaintsView.as_view(), name='official_complaints_view'),
    path('complaint/detail/<int:pk>/', views.ComplaintDetailView.as_view(), name='complaint_detail'),
    path('base-update/', views.BaseTemplateUpdateView.as_view(), name='base_template_update'),
    path('profile/edit/', views.OfficialProfileUpdateView.as_view(), name='edit_profile'),
    path('profile/change-password/', views.ChangePasswordView.as_view(), name='change_password'),
    path('delete-profile/', views.OfficialDeleteProfileView.as_view(), name='delete_profile'),
]