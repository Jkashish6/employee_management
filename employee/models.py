from django.contrib.auth.models import AbstractUser, Group, Permission
from django.db import models
from django.utils import timezone
from datetime import date
import calendar


class User(AbstractUser):
    class Role(models.TextChoices):
        HR = 'HR', 'HR'
        MANAGER = 'MANAGER', 'Manager'
        EMPLOYEE = 'EMPLOYEE', 'Employee'

    role = models.CharField(
        max_length=20,
        choices=Role.choices,
        default=Role.EMPLOYEE,
        help_text="User role in the organization"
    )

    # Manager → Employee relationship
    manager = models.ForeignKey(
        'self',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='team_members',
        limit_choices_to={'role': 'MANAGER'},
        help_text="Manager who supervises this user"
    )

    # Fix clashes with auth groups/permissions
    groups = models.ManyToManyField(
        Group,
        related_name='custom_user_set',
        blank=True,
        help_text='The groups this user belongs to.'
    )
    user_permissions = models.ManyToManyField(
        Permission,
        related_name='custom_user_set',
        blank=True,
        help_text='Specific permissions for this user.'
    )

    def __str__(self):
        return f"{self.get_full_name()} ({self.role})"

    @property
    def is_hr(self):
        return self.role == 'HR'

    @property
    def is_manager(self):
        return self.role == 'MANAGER'

    @property
    def is_employee_only(self):
        return self.role == self.Role.EMPLOYEE

    @property
    def is_staff_member(self):
        return self.role in [self.Role.HR, self.Role.MANAGER]


# Remove UserRole model – not needed anymore
# class UserRole(models.Model): → DELETE THIS ENTIRE MODEL

# === ADD THESE TWO MODELS ===

class Department(models.Model):
    name = models.CharField(max_length=100, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return self.name


class Designation(models.Model):
    department = models.ForeignKey(Department, on_delete=models.CASCADE, related_name='designations')
    designation_name = models.CharField(max_length=100)
    base_salary = models.DecimalField(max_digits=12, decimal_places=2)
    is_managerial = models.BooleanField(default=False, help_text="Is this a manager-level role?")

    class Meta:
        unique_together = ('department', 'designation_name')
        ordering = ['department__name', 'designation_name']

    def __str__(self):
        return f"{self.designation_name} ({self.department.name}) - ₹{self.base_salary}"
    
class Employee(models.Model):
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name='employee_profile'
    )
    firstname = models.CharField(max_length=50)
    lastname = models.CharField(max_length=50)
    phone = models.CharField(max_length=15, blank=True, null=True)
    email = models.EmailField(blank=True, null=True)
    dob = models.DateField("Date of Birth", null=True, blank=True)
    address = models.TextField(blank=True, null=True)
    # REMOVE this line:
# designation = models.ForeignKey(Designation, ...)

# REPLACE with:
    designation = models.ForeignKey(
    Designation,
    on_delete=models.SET_NULL,
    null=True,
    blank=True,
    related_name='employees'
    )
    department = models.ForeignKey(
    Department,
    on_delete=models.SET_NULL,
    null=True,
    blank=True,
    related_name='members'
    )
    join_date = models.DateField("Join Date", default=timezone.now)
    status = models.BooleanField("Active", default=True)

    class Meta:
        ordering = ['firstname', 'lastname']

    def __str__(self):
        return f"{self.firstname} {self.lastname}"

    @property
    def full_name(self):
        return f"{self.firstname} {self.lastname}"

    @property
    def assigned_manager(self):
        return self.user.manager

    @property
    def manager_name(self):
        return self.user.manager.get_full_name() if self.user.manager else "No Manager"


class Attendance(models.Model):
    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name='attendances')
    date = models.DateField(default=timezone.now)

    first_login = models.DateTimeField(null=True, blank=True)
    last_logout = models.DateTimeField(null=True, blank=True)

    # Legacy fields (keep for now if needed)
    login_time = models.DateTimeField(null=True, blank=True)
    logout_time = models.DateTimeField(null=True, blank=True)

    work_status = models.CharField(
        max_length=20,
        choices=[
            ('Full Day', 'Full Day'),
            ('Half Day', 'Half Day'),
            ('Absent', 'Absent'),
        ],
        default='Absent'
    )
    leave_type = models.CharField(max_length=50, blank=True, null=True)

    class Meta:
        unique_together = ('employee', 'date')
        ordering = ['-date']

    def __str__(self):
        return f"{self.employee} - {self.date} ({self.work_status})"

    @property
    def hours_worked(self):
        if self.first_login and self.last_logout:
            delta = self.last_logout - self.first_login
            return round(delta.total_seconds() / 3600, 2)
        return 0.0


class Leave(models.Model):
    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name='leaves')
    start_date = models.DateField()
    end_date = models.DateField()
    reason = models.TextField()
    leave_type = models.CharField(
        max_length=20,
        choices=[('Casual', 'Casual'), ('Duty', 'Duty'), ('Sick', 'Sick')],
        default='Casual'
    )
    status = models.CharField(
        max_length=20,
        choices=[
            ('Pending', 'Pending'),
            ('Approved', 'Approved'),
            ('Partially Approved', 'Partially Approved'),
            ('Rejected', 'Rejected'),
        ],
        default='Pending'
    )
    approved_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True, related_name='approved_leaves'
    )
    approved_start_date = models.DateField(null=True, blank=True)
    approved_end_date = models.DateField(null=True, blank=True)

    class Meta:
        ordering = ['-start_date']

    def __str__(self):
        return f"{self.employee} ({self.leave_type}) {self.start_date} → {self.end_date}"


class Task(models.Model):
    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name='tasks')
    task_name = models.CharField(max_length=200)
    task_desc = models.TextField(blank=True)
    assigned_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    status = models.CharField(
        max_length=20,
        choices=[
            ('Pending', 'Pending'),
            ('In Progress', 'In Progress'),
            ('Completed', 'Completed'),
        ],
        default='Pending'
    )
    progress = models.PositiveIntegerField(default=0, help_text="0-100%")
    start_date = models.DateField(default=timezone.now)
    due_date = models.DateField()

    class Meta:
        ordering = ['-due_date']

    def __str__(self):
        return f"{self.task_name} → {self.employee}"


class SubTask(models.Model):
    task = models.ForeignKey(Task, on_delete=models.CASCADE, related_name='subtasks')
    name = models.CharField(max_length=200)
    completed = models.BooleanField(default=False)

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        self.task.update_progress()

    def __str__(self):
        return f"{self.name} [{'Completed' if self.completed else 'Pending'}]"

class Salary(models.Model):
    employee = models.ForeignKey(
        Employee,
        on_delete=models.CASCADE,
        related_name='salaries',
        null=True, blank=True   # ← temporarily allow null
    )
    month = models.PositiveSmallIntegerField(null=True, blank=True)
    year = models.PositiveIntegerField(null=True, blank=True)
    basic_salary = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    days_worked = models.DecimalField(max_digits=5, decimal_places=1, null=True, blank=True)
    tds = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    professional_tax = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    final_salary = models.DecimalField(max_digits=12, decimal_places=2)
    generated_at = models.DateTimeField(auto_now_add=True)


    class Meta:
        unique_together = ('employee', 'month', 'year')
        ordering = ['-year', '-month']

    def __str__(self):
        return f"{self.employee} - {calendar.month_name[self.month]} {self.year}"


class Holiday(models.Model):
    date = models.DateField(unique=True)
    name = models.CharField(max_length=100)

    class Meta:
        ordering = ['-date']

    def __str__(self):
        return f"{self.name} ({self.date})"
    

class Feedback(models.Model):
    employee = models.ForeignKey(
        Employee, 
        on_delete=models.CASCADE, 
        related_name='feedbacks'  # ← THIS LINE WAS MISSING!
    )
    feedback_text = models.TextField()
    rating = models.IntegerField(choices=[(i, str(i)) for i in range(1, 6)], default=5)
    given_by = models.ForeignKey(User, on_delete=models.CASCADE)
    given_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Feedback for {self.employee}"