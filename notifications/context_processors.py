# notifications/context_processors.py
from .models import Notification

def notifications(request):
    if request.user.is_authenticated:
        # Fetch only unread notifications for the count and initial display
        # Select related actor to avoid extra queries when accessing actor details in the template
        unread_notifications = Notification.objects.filter(
            recipient=request.user, unread=True
        ).select_related('actor')[:15] # Limit initial load for performance

        return {
            'unread_notifications': unread_notifications, # Passed to the slider template
            'unread_notification_count': Notification.objects.filter(recipient=request.user, unread=True).count() # Efficient count
        }
    return {}