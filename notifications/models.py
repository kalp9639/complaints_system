# notifications/models.py
from django.db import models
from django.contrib.auth.models import User
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.utils import timezone
from django.urls import reverse

class Notification(models.Model):
    recipient = models.ForeignKey(User, on_delete=models.CASCADE, related_name='notifications')
    actor = models.ForeignKey(User, on_delete=models.CASCADE, related_name='actions', null=True, blank=True)
    verb = models.CharField(max_length=255) # e.g., 'submitted a', 'updated status of your complaint #123 to "Resolved"'

    # Target: The main object (e.g., Complaint)
    target_content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE, related_name='target_notifications', null=True, blank=True)
    target_object_id = models.PositiveIntegerField(null=True, blank=True)
    target = GenericForeignKey('target_content_type', 'target_object_id')

    # Action Object: Optional secondary object (e.g., ComplaintUpdate)
    action_object_content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE, related_name='action_notifications', null=True, blank=True)
    action_object_object_id = models.PositiveIntegerField(null=True, blank=True)
    action_object = GenericForeignKey('action_object_content_type', 'action_object_object_id')

    timestamp = models.DateTimeField(default=timezone.now)
    unread = models.BooleanField(default=True, db_index=True)

    class Meta:
        ordering = ['-timestamp'] # Show newest first
        indexes = [
            models.Index(fields=['recipient', 'unread']), # Optimize fetching unread notifications
        ]

    def __str__(self):
        parts = [str(self.actor)] if self.actor else []
        parts.append(self.verb)
        # Avoid adding target details here if the verb already includes them
        # if self.target:
        #     parts.append(str(self.target))
        return " ".join(parts)

    def mark_as_read(self):
        if self.unread:
            self.unread = False
            self.save(update_fields=['unread']) # Optimize save

    def mark_as_unread(self):
        if not self.unread:
            self.unread = True
            self.save(update_fields=['unread']) # Optimize save

    # This method helps get the URL for redirection
    def get_redirect_url(self):
        if self.target:
            try:
                # Assumes target has get_absolute_url
                return self.target.get_absolute_url()
            except AttributeError:
                pass
        # Fallback if no target URL
        return reverse('home') # Or a dedicated notifications page
