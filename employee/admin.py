# employee/admin.py
from django.contrib import admin
from .models import Employee, Designation, Task, Leave, Attendance, Salary, Holiday, SubTask
from employee.models import User  # ← CORRECT IMPORT

@admin.register(User)
class UserAdmin(admin.ModelAdmin):
    list_display = ('username', 'first_name', 'last_name', 'role', 'email')
    list_filter = ('role',)
    search_fields = ('username', 'first_name', 'last_name')

# Register other models
admin.site.register(Employee)
admin.site.register(Designation)
admin.site.register(Task)
admin.site.register(Leave)
admin.site.register(Attendance)
admin.site.register(Salary)
admin.site.register(Holiday)
admin.site.register(SubTask)