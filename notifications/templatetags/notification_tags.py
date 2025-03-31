# notifications/templatetags/notification_tags.py
from django import template
from django.utils.html import format_html

register = template.Library()

@register.simple_tag
def status_badge(status_string):
    """
    Generates a Bootstrap badge span based on the status string.
    """
    status_lower = status_string.lower()
    if 'resolved' in status_lower:
        badge_class = 'bg-success'
    elif 'in progress' in status_lower:
        badge_class = 'bg-primary' # Or bg-info
    elif 'pending' in status_lower:
        badge_class = 'bg-danger' # Or bg-warning
    else:
        badge_class = 'bg-secondary' # Default

    # Use format_html to prevent potential XSS if status_string were user-provided (though unlikely here)
    return format_html('<span class="badge {}">{}</span>', badge_class, status_string)