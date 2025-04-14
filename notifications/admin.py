# notifications/admin.py

from django.contrib import admin
from .models import Notification

@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ('recipient', 'actor', 'verb', 'target', 'action_object', 'timestamp', 'unread')
    list_filter = ('unread', 'timestamp', 'target_content_type') # Filter by read status, time, or target model type
    search_fields = ('recipient__username', 'actor__username', 'verb') # Allow searching
    readonly_fields = ('target', 'action_object') # Display GFKs read-only