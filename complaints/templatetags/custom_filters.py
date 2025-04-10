# complaints/templatetags/custom_filters.py
from django import template
from datetime import timedelta

register = template.Library()

@register.filter
def add_days(value, days):
    # Basic check if value is valid before adding timedelta
    if value:
         try:
             return value + timedelta(days=int(days))
         except (ValueError, TypeError):
             return value # Return original value on error
    return None