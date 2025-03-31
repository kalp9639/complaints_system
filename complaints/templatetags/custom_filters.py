from django import template
from datetime import timedelta

register = template.Library()

@register.filter
def add_days(value, days):
    return value + timedelta(days=days)
