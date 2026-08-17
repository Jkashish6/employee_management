# employee/templatetags/calendar_extras.py

from django import template

register = template.Library()

@register.filter
def get_item(dictionary, key):
    """
    Safe version: if dictionary is None or key not found, return None instead of crashing
    """
    if dictionary is None:
        return None
    return dictionary.get(key)

@register.filter
def mod(value, arg):
    try:
        return int(value) % int(arg)
    except (ValueError, TypeError, ZeroDivisionError):
        return 0