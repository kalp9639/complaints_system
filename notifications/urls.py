# notifications/urls.py
from django.urls import path
from . import views

# app_name = 'notifications' # Optional: Add namespace if needed

urlpatterns = [
    path('mark-all-read/', views.MarkAllNotificationsReadView.as_view(), name='mark_all_notifications_read'),
    path('redirect/<int:notification_id>/', views.NotificationRedirectView.as_view(), name='notification_redirect'),
    path('all/', views.AllNotificationsListView.as_view(), name='all_notifications_list'),
]