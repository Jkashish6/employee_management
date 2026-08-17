# employee/templatetags/dashboard_extras.py
from django import template

register = template.Library()

@register.filter
def lt(date1, date2):
    """Usage: {% if task.due_date|lt:today_date %}"""
    try:
        return date1 < date2
    except:
        return False