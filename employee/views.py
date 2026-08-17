# employee/views.py
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from employee.models import User
from django.utils import timezone
from django.db import transaction
from .models import Employee, Leave, Task, SubTask, Salary, Attendance, User,  Designation, Holiday, Department, Feedback
import random
import string
import calendar
from django.contrib import messages
from django.core.mail import send_mail
from django.conf import settings
from datetime import datetime, timedelta
from calendar import Calendar
from django.db.models import Count
import logging
from django.http import HttpResponse
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from io import BytesIO
from datetime import date
from django.core.mail import EmailMessage
from django.template.loader import render_to_string
from django.utils.html import strip_tags
from django.db.models import Sum
from django.core.paginator import Paginator
import csv
from django.views.decorators.cache import never_cache
from .models import Holiday

logger = logging.getLogger(__name__)


# ==============================================================
# HELPER FUNCTIONS
# ==============================================================

def generate_username(firstname, lastname):
    """Generate unique username like john.doe, john.doe1, etc."""
    base = f"{firstname.lower()}.{lastname.lower()}"
    username = base
    counter = 1
    while User.objects.filter(username=username).exists():
        username = f"{base}{counter}"
        counter += 1
    return username


def generate_password(length=12):
    """Generate strong random password"""
    characters = string.ascii_letters + string.digits + "!@#$%^&*"
    return ''.join(random.choice(characters) for _ in range(length))


def get_today_attendance(employee):
    """Get or create today's attendance + update first login"""
    today = timezone.localdate()
    now = timezone.now()

    attendance, created = Attendance.objects.get_or_create(
        employee=employee,
        date=today,
        defaults={
            'first_login': now,
            'last_logout': None,
            'login_time': now,
            'work_status': 'Absent'
        }
    )

    if not created and attendance.first_login is None:
        attendance.first_login = now
        attendance.login_time = now
        attendance.save(update_fields=['first_login', 'login_time'])

    return attendance, created

from django.http import JsonResponse

def get_designations(request):
    dept_id = request.GET.get('dept')
    if not dept_id:
        return JsonResponse([], safe=False)
    designations = Designation.objects.filter(department_id=dept_id).values(
        'id', 'designation_name', 'base_salary', 'is_managerial'
    )
    return JsonResponse(list(designations), safe=False)


# ==============================================================
# 1. LOGIN VIEW – Fully Updated for Role-Based Redirect
# ==============================================================

def user_login(request):
    # No need to redirect authenticated users here — let @login_required handle it elsewhere
    if request.method == 'POST':
        username = request.POST.get('username', '').strip()
        password = request.POST.get('password', '')

        if not username or not password:
            messages.error(request, "Please enter both username and password.")
            return render(request, 'login.html')

        user = authenticate(request, username=username, password=password)

        if user is not None:
            login(request, user)

            # ============== ROLE-BASED REDIRECT ==============
            if user.role == 'HR':
                messages.success(request, f"Welcome back, HR {user.get_full_name()}!")
                return redirect('employee:admin_dashboard')

            elif user.role == 'MANAGER':
                messages.success(request, f"Welcome, Manager {user.get_full_name()}!")
                return redirect('employee:admin_dashboard')  # Managers use same dashboard as HR

            elif user.role == 'EMPLOYEE':
                try:
                    # CORRECT WAY — your OneToOneField uses default related_name → "employee"
                    employee = user.employee_profile   # ← Fixed: was user.employee_profile

                    attendance, created = get_today_attendance(employee)

                    login_time = attendance.first_login.strftime('%I:%M %p') if attendance.first_login else "N/A"

                    if created or (attendance.first_login and attendance.first_login.date() == timezone.now().date()):
                        messages.success(request, f"Welcome back! Logged in at {login_time}")
                    else:
                        messages.info(request, f"Welcome! First login today was at {login_time}")

                    return redirect('employee:employee_dashboard')

                except Employee.DoesNotExist:
                    # This means the Employee profile really doesn't exist
                    logger.error(f"Employee profile missing for user: {user.username}")
                    messages.error(request, "Your profile is incomplete. Contact HR.")
                    logout(request)
                    return redirect('employee:login')

                except Exception as e:
                    # Any other unexpected error
                    logger.error(f"Login error for employee {user.username}: {e}")
                    messages.error(request, "An error occurred. Please try again or contact HR.")
                    logout(request)
                    return redirect('employee:login')

            else:
                messages.error(request, "Unknown user role.")
                logout(request)
                return redirect('employee:login')

        else:
            messages.error(request, "Invalid username or password.")

    return render(request, 'login.html')# ==============================================================
# 2. LOGOUT VIEW – Smart Attendance Update on Logout
# ==============================================================

# ==============================================================
# 2. LOGOUT VIEW – Records logout time for Employee & Manager
# ==============================================================
def user_logout(request):
    if not request.user.is_authenticated:
        return redirect('employee:login')

    # Record logout for both EMPLOYEE and MANAGER
    if request.user.role in ['EMPLOYEE', 'MANAGER']:
        try:
            # Get the Employee profile (exists for both roles)
            employee = request.user.employee_profile
            today = timezone.localdate()
            now = timezone.now()

            # Get or create today's attendance
            attendance, created = Attendance.objects.get_or_create(
                employee=employee,
                date=today,
                defaults={
                    'first_login': now,
                    'last_logout': now,
                    'work_status': 'Half Day'  # will be updated below
                }
            )

            # Update last logout
            attendance.last_logout = now
            attendance.logout_time = now

            # Calculate actual hours worked
            if attendance.first_login:
                if not attendance.last_logout:
                    attendance.last_logout = now

                delta = attendance.last_logout - attendance.first_login
                hours = delta.total_seconds() / 3600
                attendance.hours_worked = round(hours, 2)

                if hours >= 8:
                    attendance.work_status = 'Full Day'
                elif hours >= 4:
                    attendance.work_status = 'Half Day'
                else:
                    attendance.work_status = 'Half Day'

                attendance.save()

                logout_time = now.strftime('%I:%M %p')
                messages.success(request, f"Logged out at {logout_time}. Total hours today: {hours:.2f}")

        except Exception as e:
            logger.error(f"Logout error for {request.user.username}: {e}")

    logout(request)
    return redirect('employee:login')

# ==============================================================
# DEPARTMENT MANAGEMENT – ONLY HR CAN ACCESS
# ==============================================================

# ==============================================================
# NEW: DEPARTMENT MANAGEMENT – FULLY MATCHES YOUR STYLE
# ==============================================================


@login_required
def add_department(request):
    if request.user.role != 'HR':
        return redirect('employee:admin_dashboard')

    if request.method == 'POST':
        name = request.POST['name'].strip()
        if not name:
            messages.error(request, "Department name is required.")
        elif Department.objects.filter(name__iexact=name).exists():
            messages.error(request, f"Department '{name}' already exists.")
        else:
            Department.objects.create(name=name)
            messages.success(request, f"Department '{name}' added successfully!")
            # FIXED: Redirect to dashboard with departments section
            return redirect('employee:admin_dashboard')  # This is safe

    return render(request, 'add_department.html')


@login_required
def edit_department(request, dept_id):
    if request.user.role != 'HR':
        return redirect('employee:admin_dashboard')

    dept = get_object_or_404(Department, id=dept_id)

    if request.method == 'POST':
        new_name = request.POST['name'].strip()
        if not new_name:
            messages.error(request, "Department name cannot be empty.")
        elif Department.objects.filter(name__iexact=new_name).exclude(id=dept_id).exists():
            messages.error(request, f"Department '{new_name}' already exists.")
        else:
            dept.name = new_name
            dept.save()
            messages.success(request, f"Department updated to '{new_name}'.")
            return redirect('employee:admin_dashboard')

    return render(request, 'edit_department.html', {'department': dept})


@login_required
def delete_department(request, dept_id):
    if request.user.role != 'HR':
        return redirect('employee:admin_dashboard')

    dept = get_object_or_404(Department, id=dept_id)
    if Employee.objects.filter(department=dept).exists():
        messages.error(request, f"Cannot delete '{dept.name}' — employees are assigned.")
    else:
        messages.success(request, f"Department '{dept.name}' deleted.")
        dept.delete()
    return redirect('employee:admin_dashboard')# --------------------------------------------------------------
# 1. LOGIN
# --------------------------------------------------------------
# def user_login(request):
#     if request.method == 'POST':
#         username = request.POST['username']  # ← Fixed: removed the garbage "テスト"
#         password = request.POST['password']
#         user = authenticate(request, username=username, password=password)
        
#         if user is not None:
#             login(request, user)

#             if user.is_admin:
#                 return redirect('employee:admin_dashboard')
#             elif user.is_employee:
#                 try:
#                     employee = Employee.objects.get(user=user)
#                     att, created = get_today_attendance(employee)

#                     if created:
#                         messages.success(request, f"Welcome! First login recorded at {att.first_login.strftime('%H:%M')}")
#                     else:
#                         messages.info(request, f"Welcome back! First login today was at {att.first_login.strftime('%H:%M')}")

#                     return redirect('employee:employee_dashboard', employee_id=employee.id)

#                 except Employee.DoesNotExist:
#                     messages.error(request, "Employee profile not found.")
#                     return render(request, 'login.html', {'error': 'Profile error'})
#         else:
#             messages.error(request, "Invalid credentials.")
    
#     return render(request, 'login.html')
# # --------------------------------------------------------------
# # 2. LOGOUT
# # --------------------------------------------------------------
# def user_logout(request):
#     if request.user.is_authenticated and request.user.is_employee:
#         try:
#             employee = Employee.objects.get(user=request.user)
#             now = timezone.now()
#             att, _ = get_today_attendance(employee)

#             att.last_logout = now
#             att.logout_time = now
#             att.save(update_fields=['last_logout', 'logout_time'])

#             if att.first_login and att.last_logout:
#                 delta = att.last_logout - att.first_login
#                 hours = delta.total_seconds() / 3600
#                 if hours >= 8:
#                     att.work_status = 'Full Day'
#                 elif hours >= 4:
#                     att.work_status = 'Half Day'
#                 else:
#                     att.work_status = 'Absent'
#             else:
#                 att.work_status = 'Absent'

#             att.save(update_fields=['work_status'])
#             messages.success(request, f"Logged out at {att.last_logout.strftime('%H:%M')}. Have a good day!")

#         except Employee.DoesNotExist:
#             logger.error(f"No Employee for user {request.user.username} during logout")
#         except Exception as e:
#             logger.error(f"Logout error: {e}")

#     logout(request)
#     return redirect('employee:login')

from django.db.models import Q, Count
from django.core.paginator import Paginator
from django.http import HttpResponse, JsonResponse
import csv
from django.contrib.auth.decorators import login_required
from django.views.decorators.cache import never_cache
from django.db.models import Q, Count
from django.core.paginator import Paginator
from django.http import HttpResponse
import csv
from django.contrib.auth.decorators import login_required
from django.views.decorators.cache import never_cache

@never_cache
@login_required
def admin_dashboard(request):
    if request.user.role not in ['HR', 'MANAGER']:
        return redirect('employee:login')

    is_hr = request.user.role == 'HR'
    section = request.GET.get("section", "dashboard")

    # ==================================================================
    # 1. ALWAYS LOAD DEPARTMENTS & DESIGNATIONS
    # ==================================================================
    departments = Department.objects.all().order_by('name')
    designations = Designation.objects.select_related('department')\
        .all().order_by('department__name', 'designation_name')

    # ==================================================================
    # 2. EMPLOYEES — HR SEES ALL, MANAGERS SEE THEIR TEAM + THEMSELVES
    # ==================================================================
    if is_hr:
        employees_qs = Employee.objects.select_related('department', 'designation', 'user')
    else:
        # CORRECT: Your User → Employee is called 'employee_profile'
        manager_dept = request.user.employee_profile.department
        employees_qs = Employee.objects.filter(
            Q(department=manager_dept) | Q(user=request.user)
        ).select_related('department', 'designation', 'user').distinct()

    # ==================================================================
    # 3. PAGINATION FOR EMPLOYEES
    # ==================================================================
    employee_paginator = Paginator(employees_qs.order_by('-id'), 10)
    emp_page = request.GET.get('emp_page', 1)
    employees = employee_paginator.get_page(emp_page)

    # ==================================================================
    # 4. TASKS & LEAVES
    # ==================================================================
    tasks_qs = Task.objects.select_related('employee__department')
    if not is_hr:
        tasks_qs = tasks_qs.filter(employee__department=manager_dept)

    task_paginator = Paginator(tasks_qs.order_by('-id'), 10)
    task_page = request.GET.get('task_page', 1)
    tasks = task_paginator.get_page(task_page)

    pending_leaves = Leave.objects.filter(status="Pending").select_related('employee__department')
    if not is_hr:
        pending_leaves = pending_leaves.filter(employee__user__manager=request.user)

    # ==================================================================
    # 5. MANAGERS WITH TEAM COUNT — FIXED FOR employee_profile
    # ==================================================================# ==================================================================
# 5. MANAGERS WITH TEAM COUNT — FIXED (CORRECT)
# ==================================================================
    managers_with_teams = User.objects.filter(role='MANAGER') \
    .select_related('employee_profile__department', 'employee_profile__designation') \
    .annotate(
        team_count=Count('team_members', distinct=True)
    )


    # ==================================================================
    # 6. FINAL CONTEXT
    # ==================================================================
    context = {
        'section': section,
        'is_hr': is_hr,
        'is_manager': request.user.role == 'MANAGER',

        'employees': employees,
        'departments': departments,
        'designations': designations,
        'tasks': tasks,
        'leaves': pending_leaves.order_by('-start_date'),
        'managers_with_teams': managers_with_teams,

        'total_employees': employees_qs.count(),
        'total_departments': departments.count(),
        'total_designations': designations.count(),
        'total_tasks': tasks_qs.count(),
        'total_leave_requests': pending_leaves.count(),
        'total_tasks_completed': tasks_qs.filter(status="Completed").count(),
    }

    # ==================================================================
    # 7. EXCEL EXPORT — INCLUDES ROLE
    # ==================================================================
    export = request.GET.get('export')
    if export == 'excel' and section == 'employees':
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="employees.csv"'
        writer = csv.writer(response)
        writer.writerow(['Name', 'Role', 'Department', 'Designation', 'Email', 'Phone', 'Join Date'])
        for emp in employees_qs:
            role = "Manager" if emp.user.role == 'MANAGER' else "Employee"
            writer.writerow([
                f"{emp.firstname} {emp.lastname}",
                role,
                emp.department.name if emp.department else "—",
                emp.designation.designation_name if emp.designation else "—",
                emp.email or "—",
                emp.phone or "—",
                emp.join_date.strftime('%Y-%m-%d') if emp.join_date else "—"
            ])
        return response

    return render(request, "admin_dashboard.html", context)
# ==================================================================
# AJAX VIEW TO GET TEAM MEMBERS
# ==================================================================
@login_required
def get_team(request):
    if request.user.role != 'HR':
        return JsonResponse({'error': 'Unauthorized'}, status=403)

    manager_id = request.GET.get('manager_id')
    if not manager_id:
        return JsonResponse({'employees': []})

    try:
        manager = User.objects.get(id=manager_id, role='MANAGER')
        team = Employee.objects.filter(user__manager=manager)\
            .select_related('designation', 'department')

        employees_data = []
        for emp in team:
            employees_data.append({
                'id': emp.id,
                'name': f"{emp.firstname} {emp.lastname}",
                'designation': emp.designation.designation_name,
                'department': emp.department.name,
                'completed_tasks': emp.tasks.filter(status='Completed').count(),
                'in_progress_tasks': emp.tasks.filter(status='In Progress').count(),
                'pending_tasks': emp.tasks.filter(status='Pending').count(),
            })

        return JsonResponse({
            'manager_name': manager.get_full_name(),
            'employees': employees_data
        })
    except User.DoesNotExist:
        return JsonResponse({'employees': []})
# --------------------------------------------------------------
# EMPLOYEE DASHBOARD – Only the logged-in employee can view their own data
# --------------------------------------------------------------

@login_required
def employee_dashboard(request):
    if request.user.role != 'EMPLOYEE':
        messages.error(request, "Access denied. This page is for employees only.")
        return redirect('employee:admin_dashboard')
    
    try:
        # In employee_dashboard view — before context
        employee = request.user.employee_profile
    except Employee.DoesNotExist:
        messages.error(request, "Employee profile not found.")
        return redirect('employee:login')
    
    # ... rest of your code
    # 100% SAFE DESIGNATION NAME — THIS FIXES EVERYTHING!
    designation_name = "Employee"
    if employee.designation:
        designation_name = employee.designation.designation_name or "Employee"

    # No need for employee_id in URL — much cleaner and safer
    # Old: /dashboard/5 → New: /dashboard/

    # Current year for leave balance
    current_year = timezone.now().year
    today = date.today()

    # === TASKS ===
    tasks = Task.objects.filter(employee=employee).select_related('assigned_by')
    task_status_data = {
        'Pending': tasks.filter(status='Pending').count(),
        'In Progress': tasks.filter(status='In Progress').count(),
        'Completed': tasks.filter(status='Completed').count(),
    }
    total_tasks_completed = tasks.filter(status='Completed').count()

    # === LEAVES ===
    leaves = Leave.objects.filter(employee=employee).order_by('-start_date')
    approved_leaves_this_year = leaves.filter(status='Approved', start_date__year=current_year).count()
    leave_balance = {
        'taken': approved_leaves_this_year,
        'remaining': max(30 - approved_leaves_this_year, 0),  # Standard 30 leaves/year
        'total_allowed': 30
    }

    # === SALARY ===
    salaries = Salary.objects.filter(employee=employee).order_by('-year', '-month')[:12]  # Last 12 months

    # === ATTENDANCE ===
    def calculate_hours(first_login, last_logout):
        if first_login and last_logout and last_logout > first_login:
            hours = (last_logout - first_login).total_seconds() / 3600
            return round(hours, 2)
        return 0.0

    recent_attendance = Attendance.objects.filter(employee=employee).order_by('-date')[:30]
    attendance_summary = {
        'Full Day': 0,
        'Half Day': 0,
        'Absent': 0,
        'On Leave': 0,
    }

    attendance_list = []
    for att in recent_attendance:
        hours = calculate_hours(att.first_login, att.last_logout)
        status = att.work_status
        if att.leave_type and att.work_status == 'Absent':
            status = f"On Leave ({att.leave_type})"

        attendance_summary[att.work_status if att.work_status != 'Absent' or not att.leave_type else 'On Leave'] += 1

        attendance_list.append({
            'date': att.date,
            'day': att.date.strftime('%A'),
            'status': status,
            'hours': hours if hours > 0 else '-',
            'first_login': att.first_login.strftime('%I:%M %p') if att.first_login else '-',
            'last_logout': att.last_logout.strftime('%I:%M %p') if att.last_logout else '-',
        })

    # Monthly attendance trend (last 6 months)
    monthly_trend = []
    for i in range(5, -1, -1):
        month_date = today.replace(day=1) - timezone.timedelta(days=1)
        month_date = month_date.replace(month=month_date.month - i if month_date.month > i else 12 - i)
        month = month_date.month
        year = month_date.year

        count = Attendance.objects.filter(
            employee=employee,
            date__month=month,
            date__year=year,
            work_status='Full Day'
        ).count()

        monthly_trend.append({
            'month': calendar.month_name[month][:3],
            'full_days': count,
        })
        # employee_dashboard view ke context mein ye line add kar do
    feedbacks = Feedback.objects.filter(employee=employee).select_related('given_by').order_by('-given_at')

    context = {
        'employee': employee,
        'designation_name': designation_name,
        'tasks': tasks,
        'task_status_data': task_status_data,
        'total_tasks_completed': total_tasks_completed,

        'leaves': leaves,
        'leave_balance': leave_balance,

        'salaries': salaries,
        'latest_salary': salaries.first(),

        'attendance_list': attendance_list,
        'attendance_summary': attendance_summary,
        'monthly_trend': monthly_trend,

        'current_month': today.strftime('%B %Y'),
        'feedbacks': feedbacks,
    }

    return render(request, 'employee_dashboard.html', context)# --------------------------------------------------------------
# LEAVE REQUEST
# --------------------------------------------------------------
# --------------------------------------------------------------
# EMPLOYEE: Submit Leave Request
# --------------------------------------------------------------
@login_required
def leave_request(request):
    # Only employees (including managers too, but they can apply as employees)
    if not hasattr(request.user, 'employee_profile'):
        messages.error(request, "Employee profile not found.")
        return redirect('employee:login')

    employee = request.user.employee_profile  # Clean access

    current_year = timezone.now().year

    # Count approved leaves this year
    approved_casual = Leave.objects.filter(
        employee=employee,
        leave_type='Casual',
        status='Approved',
        start_date__year=current_year
    ).count()

    approved_duty = Leave.objects.filter(
        employee=employee,
        leave_type='Duty',
        status='Approved',
        start_date__year=current_year
    ).count()

    remaining_casual = max(12 - approved_casual, 0)
    remaining_duty = max(10 - approved_duty, 0)

    if request.method == 'POST':
        start_date_str = request.POST.get('start_date')
        end_date_str = request.POST.get('end_date')
        reason = request.POST.get('reason', '').strip()
        leave_type = request.POST.get('leave_type')

        if not all([start_date_str, end_date_str, reason, leave_type]):
            messages.error(request, "All fields are required.")
            return render(request, 'leave_request.html', {
                'remaining_casual_leaves': remaining_casual,
                'remaining_duty_leaves': remaining_duty,
                'today': timezone.now().date(),
            })

        try:
            start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
            end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date()
        except ValueError:
            messages.error(request, "Invalid date format.")
            return render(request, 'leave_request.html', {
                'remaining_casual_leaves': remaining_casual,
                'remaining_duty_leaves': remaining_duty,
                'today': timezone.now().date(),
            })

        if start_date > end_date:
            messages.error(request, "End date must be after start date.")
            return redirect('employee:leave_request')

        if leave_type not in ['Casual', 'Duty']:
            messages.error(request, "Invalid leave type.")
            return redirect('employee:leave_request')

        # Check leave balance
        if leave_type == 'Casual' and remaining_casual <= 0:
            messages.error(request, "You have no remaining Casual leaves for this year.")
            return redirect('employee:leave_request')
        if leave_type == 'Duty' and remaining_duty <= 0:
            messages.error(request, "You have no remaining Duty leaves for this year.")
            return redirect('employee:leave_request')

        # Create leave request
        leave = Leave.objects.create(
            employee=employee,
            start_date=start_date,
            end_date=end_date,
            reason=reason,
            leave_type=leave_type,
            status='Pending'
        )

        messages.success(request, "Leave request submitted successfully! Awaiting approval.")
        return redirect('employee:employee_dashboard')

    return render(request, 'leave_request.html', {
        'remaining_casual_leaves': remaining_casual,
        'remaining_duty_leaves': remaining_duty,
        'today': timezone.now().date(),
    })

# --------------------------------------------------------------
# APPROVE / REJECT / PARTIAL APPROVE
# --------------------------------------------------------------
# --------------------------------------------------------------
# APPROVE LEAVE – HR or Manager of the employee
# --------------------------------------------------------------
@login_required
def approve_leave(request, leave_id):
    if request.user.role not in ['HR', 'MANAGER']:
        messages.error(request, "You do not have permission to approve leaves.")
        return redirect('employee:admin_dashboard')

    leave = get_object_or_404(Leave, id=leave_id, status='Pending')
    is_hr = request.user.role == 'HR'

    # Security: Manager can only approve their team member's leave
    if not is_hr and leave.employee.user.manager != request.user:
        messages.error(request, "You can only approve leaves for your team members.")
        return redirect('employee:admin_dashboard')

    leave.status = 'Approved'
    leave.approved_by = request.user
    leave.approved_start_date = leave.start_date
    leave.approved_end_date = leave.end_date
    leave.save()

    # Mark attendance as 'Absent' with leave type
    current_date = leave.start_date
    while current_date <= leave.end_date:
        if current_date.weekday() < 5:  # Monday=0 to Friday=4
            Attendance.objects.update_or_create(
                employee=leave.employee,
                date=current_date,
                defaults={
                    'work_status': 'Absent',
                    'leave_type': f"Approved {leave.leave_type} Leave"
                }
            )
        current_date += timedelta(days=1)

    messages.success(request, f"Leave approved for {leave.employee.firstname} {leave.employee.lastname}")
    return redirect('employee:admin_dashboard')

# --------------------------------------------------------------
# PARTIAL APPROVE LEAVE – HR or Manager
# --------------------------------------------------------------
@login_required
def partial_approve_leave(request, leave_id):
    if request.user.role not in ['HR', 'MANAGER']:
        messages.error(request, "Permission denied.")
        return redirect('employee:admin_dashboard')

    leave = get_object_or_404(Leave, id=leave_id, status='Pending')
    is_hr = request.user.role == 'HR'

    if not is_hr and leave.employee.user.manager != request.user:
        messages.error(request, "You can only partially approve your team members' leaves.")
        return redirect('employee:admin_dashboard')

    if request.method == 'POST':
        try:
            approved_start = datetime.strptime(request.POST['approved_start_date'], '%Y-%m-%d').date()
            approved_end = datetime.strptime(request.POST['approved_end_date'], '%Y-%m-%d').date()

            if approved_start < leave.start_date or approved_end > leave.end_date:
                messages.error(request, "Approved dates must be within requested range.")
                return render(request, 'partial_approval.html', {'leave': leave})

            if approved_start > approved_end:
                messages.error(request, "End date cannot be before start date.")
                return render(request, 'partial_approval.html', {'leave': leave})

            leave.status = 'Partially Approved'
            leave.approved_by = request.user
            leave.approved_start_date = approved_start
            leave.approved_end_date = approved_end
            leave.save()

            # Update only approved dates
            current_date = approved_start
            while current_date <= approved_end:
                if current_date.weekday() < 5:
                    Attendance.objects.update_or_create(
                        employee=leave.employee,
                        date=current_date,
                        defaults={
                            'work_status': 'Absent',
                            'leave_type': f"Partially Approved {leave.leave_type} Leave"
                        }
                    )
                current_date += timedelta(days=1)

            messages.success(request, f"Leave partially approved for {leave.employee.firstname}")
            return redirect('employee:admin_dashboard')

        except ValueError:
            messages.error(request, "Invalid date format.")
    
    return render(request, 'partial_approval.html', {'leave': leave})

# --------------------------------------------------------------
# REJECT LEAVE – HR or Manager
# --------------------------------------------------------------
@login_required
def reject_leave(request, leave_id):
    if request.user.role not in ['HR', 'MANAGER']:
        messages.error(request, "You do not have permission to reject leaves.")
        return redirect('employee:admin_dashboard')

    leave = get_object_or_404(Leave, id=leave_id, status='Pending')
    is_hr = request.user.role == 'HR'

    if not is_hr and leave.employee.user.manager != request.user:
        messages.error(request, "You can only reject leaves of your team members.")
        return redirect('employee:admin_dashboard')

    leave.status = 'Rejected'
    leave.approved_by = request.user
    leave.save()

    messages.success(request, f"Leave request rejected for {leave.employee.firstname} {leave.employee.lastname}")
    return redirect('employee:admin_dashboard')
# --------------------------------------------------------------
# ADD EMPLOYEE
# --------------------------------------------------------------
# --------------------------------------------------------------
# ADD EMPLOYEE / MANAGER – Only HR can access
# --------------------------------------------------------------
# ==============================================================
# ADD EMPLOYEE – NOW WITH DEPARTMENT + SMART MANAGER LOGIC
# ==============================================================
@login_required
def add_employee(request):
    if request.user.role != 'HR':
        messages.error(request, "Only HR can add employees.")
        return redirect('employee:admin_dashboard')

    departments = Department.objects.all().order_by('name')
    managers = User.objects.filter(role='MANAGER').select_related('employee_profile').order_by('first_name')

    if request.method == 'POST':
        try:
            firstname = request.POST['firstname'].strip()
            lastname = request.POST['lastname'].strip()
            phone = request.POST.get('phone', '').strip()
            email = request.POST['email'].strip()
            dob_str = request.POST['dob']
            join_date_str = request.POST['join_date']
            address = request.POST.get('address', '').strip()

            department_id = request.POST['department']
            designation_id = request.POST['designation']
            manager_id = request.POST.get('manager', None)
            status = 'on' in request.POST.get('status', '')

            # Validate dates
            dob = datetime.strptime(dob_str, "%Y-%m-%d").date()
            join_date = datetime.strptime(join_date_str, "%Y-%m-%d").date()

            if join_date <= dob:
                messages.error(request, "Join date must be after date of birth.")
                return redirect('employee:add_employee')

            age_at_join = join_date.year - dob.year - ((join_date.month, join_date.day) < (dob.month, dob.day))
            if age_at_join < 18:
                messages.error(request, "Employee must be at least 18 years old.")
                return redirect('employee:add_employee')

            # Get objects
            department = get_object_or_404(Department, id=department_id)
            designation = get_object_or_404(Designation, id=designation_id)

            # Auto-determine role from designation
            role = 'MANAGER' if designation.is_managerial else 'EMPLOYEE'

            # Generate credentials
            username = generate_username(firstname, lastname)
            password = generate_password()

            # Create User
            user = User.objects.create_user(
                username=username,
                password=password,
                email=email,
                first_name=firstname,
                last_name=lastname,
                role=role
            )

            # Assign manager_user = None
            if not designation.is_managerial and manager_id:
                try:
                    manager_user = User.objects.get(id=manager_id, role='MANAGER')
                    user.manager = manager_user
                except User.DoesNotExist:
                    messages.error(request, "Selected manager not found.")
                    user.delete()
                    return redirect('employee:add_employee')

            user.save()

            # Create Employee Profile
            Employee.objects.create(
                user=user,
                firstname=firstname,
                lastname=lastname,
                phone=phone,
                email=email,
                dob=dob,
                address=address,
                designation=designation,
                department=department,
                join_date=join_date,
                status=status
            )

            # Send email
            role_name = "Manager" if role == "MANAGER" else "Employee"
            subject = 'Your EMS Account Has Been Created'
            message = f"""
Hello {firstname} {lastname},

Your {role_name} account has been successfully created!

Login Details:
→ Username: {username}
→ Password: {password}

Login URL: http://127.0.0.1:8000/login

Please change your password on first login.

Best regards,
HR Department
            """
            try:
                send_mail(subject, message, settings.EMAIL_HOST_USER, [email], fail_silently=False)
                messages.success(request, f"{role_name} {firstname} {lastname} added successfully & email sent!")
            except Exception as e:
                messages.warning(request, f"{role_name} added successfully but email failed: {e}")

            return redirect('employee:admin_dashboard')

        except Exception as e:
            messages.error(request, f"Error: {str(e)}")
            return redirect('employee:add_employee')

    return render(request, 'add_employee.html', {
        'departments': departments,
        'managers': managers,
        'today_date': date.today().isoformat(),
    })


@login_required
def add_employee_success(request, firstname, lastname):
    return render(request, 'add_employee_success.html', {
        'firstname': firstname,
        'lastname': lastname,
        'message': f"Employee {firstname} {lastname} has been added successfully!"
    })


# --------------------------------------------------------------
# EDIT EMPLOYEE
# --------------------------------------------------------------
# --------------------------------------------------------------
# EDIT EMPLOYEE / MANAGER – HR can edit anyone, Manager can edit only team members
# --------------------------------------------------------------
@login_required
def edit_employee(request, employee_id):
    # Permission check: Only HR or the employee's Manager can edit
    if request.user.role not in ['HR', 'MANAGER']:
        messages.error(request, "Access denied.")
        return redirect('employee:login')

    employee = get_object_or_404(Employee, id=employee_id)
    target_user = employee.user
    is_hr = request.user.role == 'HR'

    # Security: Manager can only edit their own team members
    if not is_hr and target_user.manager != request.user:
        messages.error(request, "You can only edit employees in your team.")
        return redirect('employee:admin_dashboard')

    if request.method == 'POST':
        try:
            firstname = request.POST['firstname'].strip()
            lastname = request.POST['lastname'].strip()
            phone = request.POST.get('phone', '').strip()
            email = request.POST['email'].strip()
            dob_str = request.POST['dob']
            join_date_str = request.POST['join_date']
            address = request.POST.get('address', '').strip()
            designation_id = request.POST['designation']

            # Convert dates
            dob = datetime.strptime(dob_str, '%Y-%m-%d').date()
            join_date = datetime.strptime(join_date_str, '%Y-%m-%d').date()

            if join_date <= dob:
                messages.error(request, "Join date must be after date of birth.")
                return redirect('employee:edit_employee', employee_id=employee_id)

            # Optional: Update role (only HR can change role)
            new_role = request.POST.get('role', target_user.role)
            if is_hr:
                if new_role not in ['EMPLOYEE', 'MANAGER']:
                    messages.error(request, "Invalid role selected.")
                    return redirect('employee:edit_employee', employee_id=employee_id)
                target_user.role = new_role
            else:
                new_role = target_user.role  # Managers can't change role

            # Optional: Re-assign manager (only if role is EMPLOYEE)
            new_manager_id = request.POST.get('manager')
            if new_role == 'EMPLOYEE':
                if new_manager_id:
                    try:
                        new_manager = User.objects.get(id=new_manager_id, role='MANAGER')
                        target_user.manager = new_manager
                    except User.DoesNotExist:
                        messages.error(request, "Invalid manager selected.")
                        return redirect('employee:edit_employee', employee_id=employee_id)
                else:
                    target_user.manager = None
            else:
                target_user.manager = None  # Managers have no manager

            # Update User model
            target_user.first_name = firstname
            target_user.last_name = lastname
            target_user.email = email
            target_user.save()

            # Update Employee model
            designation = get_object_or_404(Designation, id=designation_id)
            employee.firstname = firstname
            employee.lastname = lastname
            employee.phone = phone
            employee.email = email
            employee.dob = dob
            employee.join_date = join_date
            employee.address = address
            employee.designation = designation
            employee.status = 'on' in request.POST.get('status', '')
            employee.save()

            messages.success(request, f"{firstname} {lastname} updated successfully!")
            return redirect('employee:admin_dashboard')

        except ValueError:
            messages.error(request, "Invalid date format.")
        except Exception as e:
            messages.error(request, f"Error updating employee: {str(e)}")

        return redirect('employee:edit_employee', employee_id=employee_id)

    # GET request – show form
    context = {
        'employee': employee,
        'today_date': date.today().isoformat(),
        'is_hr': is_hr,
        'can_change_role': is_hr,

        # THESE 2 LINES WERE MISSING — NOW ADDED
        'departments': Department.objects.all().order_by('name'),
        'managers': User.objects.filter(role='MANAGER').select_related('employee_profile').order_by('first_name'),
    }
    return render(request, 'edit_employee.html', context)# --------------------------------------------------------------
# DELETE EMPLOYEE
# --------------------------------------------------------------
# --------------------------------------------------------------
# DELETE EMPLOYEE – HR can delete anyone, Manager can delete only their team
# --------------------------------------------------------------
@login_required
def delete_employee(request, employee_id):
    if request.user.role not in ['HR', 'MANAGER']:
        messages.error(request, "Access denied.")
        return redirect('employee:login')

    employee = get_object_or_404(Employee, id=employee_id)
    target_user = employee.user

    is_hr = request.user.role == 'HR'

    # Security: Manager can only delete their own team members
    if not is_hr and target_user.manager != request.user:
        messages.error(request, "You can only delete employees from your team.")
        return redirect('employee:admin_dashboard')

    full_name = f"{employee.firstname} {employee.lastname}"
    
    # Soft protection: Don't allow deleting HR or self
    if target_user.role == 'HR':
        messages.error(request, "Cannot delete HR account.")
        return redirect('employee:admin_dashboard')
    if target_user == request.user:
        messages.error(request, "You cannot delete your own account.")
        return redirect('employee:admin_dashboard')

    # Delete user + employee profile
    target_user.delete()
    employee.delete()

    messages.success(request, f"Employee '{full_name}' deleted successfully.")
    return redirect('employee:admin_dashboard')

# --------------------------------------------------------------
# ASSIGN TASK
# --------------------------------------------------------------
# --------------------------------------------------------------
# ASSIGN TASK – HR sees all, Managers see only their team
# --------------------------------------------------------------
@login_required
def assign_task(request):
    if request.user.role not in ['HR', 'MANAGER']:
        messages.error(request, "Access denied.")
        return redirect('employee:login')

    is_hr = request.user.role == 'HR'
    export = request.GET.get('export')

    # EXCEL EXPORT — NOW 100% WORKING!
    if export == 'excel':
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="all_tasks.csv"'
        writer = csv.writer(response)
        writer.writerow(['Task Name', 'Assigned To', 'Status', 'Progress (%)', 'Start Date', 'Due Date', 'Assigned By'])

        tasks = Task.objects.select_related('employee', 'assigned_by')
        if not is_hr:
            tasks = tasks.filter(employee__user__manager=request.user)

        for task in tasks:
            writer.writerow([
                task.task_name,
                f"{task.employee.firstname} {task.employee.lastname}" if task.employee else "—",
                task.status,
                task.progress,
                task.start_date.strftime('%Y-%m-%d'),
                task.due_date.strftime('%Y-%m-%d'),
                task.assigned_by.get_full_name() if task.assigned_by else "HR"
            ])
        return response

    # Normal assign task logic below...
    # HR sees all employees, Manager sees only their team
    if is_hr:
        employees = Employee.objects.select_related('user', 'designation', 'department').all()
    else:
        employees = Employee.objects.filter(
            user__manager=request.user
        ).select_related('user', 'designation', 'department')
        
    if request.method == 'POST':
        try:
            task_name = request.POST.get('task_name')
            task_desc = request.POST.get('task_desc', '')
            employee_id = request.POST.get('employee')
            start_date_str = request.POST.get('start_date')
            due_date_str = request.POST.get('due_date')

            if not all([task_name, employee_id, start_date_str, due_date_str]):
                raise ValueError("All required fields must be filled.")

            start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
            due_date = datetime.strptime(due_date_str, '%Y-%m-%d').date()

            if due_date < start_date:
                raise ValueError("Due date cannot be before start date.")

            employee = get_object_or_404(Employee, id=employee_id)

            if not is_hr and employee.user.manager != request.user:
                messages.error(request, "You can only assign tasks to your team members.")
                return redirect('employee:assign_task')

            task = Task.objects.create(
                task_name=task_name,
                task_desc=task_desc,
                employee=employee,
                assigned_by=request.user,
                start_date=start_date,
                due_date=due_date,
                status='Pending',
                progress=0
            )

            subtask_names = request.POST.getlist('subtask_name[]')
            for name in subtask_names:
                if name.strip():
                    SubTask.objects.create(task=task, name=name.strip())

            messages.success(request, f"Task assigned to {employee.firstname} {employee.lastname}.")
            return redirect('employee:admin_dashboard')

        except ValueError as ve:
            messages.error(request, str(ve))
        except Exception as e:
            messages.error(request, f"Error: {str(e)}")

    return render(request, 'assign_task.html', {
        'employees': employees,
        'is_hr': is_hr
    })
# --------------------------------------------------------------
# UPDATE TASK (Admin)
# --------------------------------------------------------------
# --------------------------------------------------------------
# UPDATE TASK – HR & Managers can edit tasks assigned to their team
# --------------------------------------------------------------
@login_required
def update_task(request, task_id):
    if request.user.role not in ['HR', 'MANAGER']:
        messages.error(request, "Access denied.")
        return redirect('employee:login')

    task = get_object_or_404(Task, id=task_id)
    employee_user = task.employee.user
    is_hr = request.user.role == 'HR'

    # Security: Manager can only update tasks of their team members
    if not is_hr and employee_user.manager != request.user:
        messages.error(request, "You can only update tasks assigned to your team.")
        return redirect('employee:admin_dashboard')

    if request.method == 'POST':
        try:
            task.task_name = request.POST.get('task_name', task.task_name)
            task.task_desc = request.POST.get('task_desc', task.task_desc)
            task.status = request.POST.get('status', task.status)
            task.progress = max(0, min(100, int(request.POST.get('progress', task.progress))))

            start_date = datetime.strptime(request.POST.get('start_date'), '%Y-%m-%d').date()
            due_date = datetime.strptime(request.POST.get('due_date'), '%Y-%m-%d').date()

            if due_date < start_date:
                messages.error(request, "Due date cannot be before start date.")
            else:
                task.start_date = start_date
                task.due_date = due_date

            task.save()

            # Update subtasks
            for subtask in task.subtasks.all():
                key = f'subtask_completed_{subtask.id}'
                completed = key in request.POST
                if subtask.completed != completed:
                    subtask.completed = completed
                    subtask.save()

            messages.success(request, f"Task '{task.task_name}' updated successfully.")
            return redirect('employee:admin_dashboard')

        except ValueError:
            messages.error(request, "Invalid date or progress value.")
        except Exception as e:
            messages.error(request, f"Error updating task: {str(e)}")

    return render(request, 'update_task.html', {
        'task': task,
        'is_hr': is_hr
    })

@login_required
def delete_task(request, task_id):
    if request.user.role not in ['HR', 'MANAGER']:
        messages.error(request, "Access denied.")
        return redirect('employee:admin_dashboard')
    
    task = get_object_or_404(Task, id=task_id)
    
    # Manager can only delete tasks from their team
    if request.user.role == 'MANAGER' and task.employee.user.manager != request.user:
        messages.error(request, "You can only delete tasks from your team.")
        return redirect('employee:admin_dashboard')
    
    task_name = task.task_name
    task.delete()
    messages.success(request, f"Task '{task_name}' deleted successfully.")
    return redirect('employee:admin_dashboard')

# --------------------------------------------------------------
# UPDATE EMPLOYEE TASK
# --------------------------------------------------------------
# --------------------------------------------------------------
# EMPLOYEE: Update My Task Progress
# --------------------------------------------------------------
@login_required
def update_employee_task(request, task_id):
    # Only the employee who owns the task can update it
    if request.user.role != 'EMPLOYEE':
        messages.error(request, "Access denied.")
        return redirect('employee:employee_dashboard')

    try:
        employee = request.user.employee_profile
    except Employee.DoesNotExist:
        messages.error(request, "Your profile is missing.")
        return redirect('employee:login')

    task = get_object_or_404(Task, id=task_id, employee=employee)

    if task.status == 'Completed':
        messages.warning(request, "This task is already completed.")
        return render(request, 'update_employee_task.html', {'task': task, 'can_edit': False})

    if request.method == 'POST':
        try:
            progress = int(request.POST.get('progress', 0))
            status = request.POST.get('status')

            if not 0 <= progress <= 100:
                messages.error(request, "Progress must be between 0 and 100.")
                return render(request, 'update_employee_task.html', {'task': task})

            valid_statuses = ['Pending', 'In Progress', 'Completed']
            if status not in valid_statuses:
                messages.error(request, "Invalid status.")
                return render(request, 'update_employee_task.html', {'task': task})

            if progress == 100:
                status = 'Completed'

            task.progress = progress
            task.status = status
            task.save()

            # Update subtasks
            for subtask in task.subtasks.all():
                key = f'subtask_completed_{subtask.id}'
                if key in request.POST:
                    subtask.completed = True
                else:
                    subtask.completed = False
                subtask.save()

            messages.success(request, "Task updated successfully!")
            return redirect('employee:employee_dashboard')
        except:
            messages.error(request, "Invalid data submitted.")

    return render(request, 'update_employee_task.html', {
        'task': task,
        'can_edit': True,
    })# --------------------------------------------------------------
# ATTENDANCE REPORT
# --------------------------------------------------------------
# --------------------------------------------------------------
# ATTENDANCE REPORT – HR sees all, Manager sees only team
# --------------------------------------------------------------
@login_required
def attendance_report(request, employee_id):
    if request.user.role not in ['HR', 'MANAGER']:
        messages.error(request, "Access denied.")
        return redirect('employee:login')

    employee = get_object_or_404(Employee, id=employee_id)

    # Security: Manager can only view their team members
    if request.user.role == 'MANAGER' and employee.user.manager != request.user:
        messages.error(request, "You can only view attendance of your team members.")
        return redirect('employee:admin_dashboard')

    # Get last 30 attendance records (this returns a LIST, not QuerySet)
    attendances = Attendance.objects.filter(employee=employee)\
        .order_by('-date')[:30]

    # Convert to list so we can safely filter
    attendances_list = list(attendances)

    # Now safely count each status
    full_days = sum(1 for a in attendances_list if a.work_status == 'Full Day')
    half_days = sum(1 for a in attendances_list if a.work_status == 'Half Day')
    absent_days = sum(1 for a in attendances_list if a.work_status == 'Absent')

    context = {
        'employee': employee,
        'attendances': attendances_list,  # Pass the list
        'full_days': full_days,
        'half_days': half_days,
        'absent_days': absent_days,
        'total_recorded': len(attendances_list),
    }
    return render(request, 'attendance_report.html', context)
# --------------------------------------------------------------
# DESIGNATION VIEWS
# --------------------------------------------------------------
# --------------------------------------------------------------
# ADD DESIGNATION – Only HR allowed# ==============================================================
# NEW: DESIGNATION MANAGEMENT – MATCHES YOUR DASHBOARD STYLE
# ==============================================================

# views.py

@login_required
def add_designation(request):
    if request.user.role != 'HR':
        return redirect('employee:admin_dashboard')

    if request.method == 'POST':
        dept_id = request.POST['department']
        name = request.POST['designation_name'].strip()
        salary = request.POST['base_salary']
        role = request.POST['role']

        if not all([dept_id, name, salary]):
            messages.error(request, "All fields are required.")
        elif Designation.objects.filter(department_id=dept_id, designation_name__iexact=name).exists():
            messages.error(request, "This designation already exists in the selected department.")
        else:
            try:
                salary = float(salary)
                Designation.objects.create(
                    department_id=dept_id,
                    designation_name=name,
                    base_salary=salary,
                    is_managerial=(role == 'MANAGER')
                )
                messages.success(request, f"Designation '{name}' added!")
                return redirect('employee:admin_dashboard')  # This is safe
            except:
                messages.error(request, "Invalid salary.")

    departments = Department.objects.all()
    return render(request, 'add_designation.html', {'departments': departments})


@login_required
def edit_designation(request, designation_id):
    if request.user.role != 'HR':
        return redirect('employee:admin_dashboard')

    designation = get_object_or_404(Designation, id=designation_id)

    if request.method == 'POST':
        dept_id = request.POST['department']
        name = request.POST['designation_name'].strip()
        salary = request.POST['base_salary']
        role = request.POST['role']

        if not all([dept_id, name, salary]):
            messages.error(request, "All fields are required.")
        elif Designation.objects.filter(department_id=dept_id, designation_name__iexact=name).exclude(id=designation.id).exists():
            messages.error(request, "This designation already exists in the department.")
        else:
            try:
                salary = float(salary)
                designation.department_id = dept_id
                designation.designation_name = name
                designation.base_salary = salary
                designation.is_managerial = (role == 'MANAGER')
                designation.save()
                messages.success(request, "Designation updated!")
                return redirect('employee:admin_dashboard')
            except:
                messages.error(request, "Invalid salary.")

    departments = Department.objects.all()
    return render(request, 'edit_designation.html', {
        'designation': designation,
        'departments': departments
    })

@login_required
def delete_designation(request, designation_id):
    if request.user.role != 'HR':
        messages.error(request, "Only HR can delete designations.")
        return redirect('employee:admin_dashboard')
    
    designation = get_object_or_404(Designation, id=designation_id)
    
    if request.method == 'POST':
        if Employee.objects.filter(designation=designation).exists():
            messages.error(request, f"Cannot delete '{designation.designation_name}' — employees are still assigned.")
        else:
            designation_name = designation.designation_name
            designation.delete()
            messages.success(request, f"Designation '{designation_name}' deleted successfully!")
        return redirect('employee:admin_dashboard')
    
    return render(request, 'delete_designation.html', {
        'designation': designation
    })# PREVIEW SALARY
# --------------------------------------------------------------
# --------------------------------------------------------------
# PREVIEW SALARY – HR sees all, Managers see only their team
# --------------------------------------------------------------
@login_required
def preview_salary(request):
    # Only HR and Managers can access this page
    if request.user.role not in ['HR', 'MANAGER']:
        messages.error(request, "You do not have permission to view salary previews.")
        return redirect('employee:admin_dashboard')

    is_hr = request.user.role == 'HR'

    # Determine which employees can the current user see?
    if is_hr:
        employees = Employee.objects.select_related('designation', 'user').all()
    else:
        employees = Employee.objects.filter(
            user__manager=request.user
        ).select_related('designation', 'user')

    selected_employee = None
    salary_preview = None

    if request.method == 'POST':
        employee_id = request.POST.get('employee_id')

        if not employee_id:
            messages.error(request, "Please select an employee.")
            return render(request, 'preview_salary.html', {
                'employees': employees,
                'is_hr': is_hr
            })

        # Get employee with security check
        try:
            employee = Employee.objects.select_related('designation').get(id=employee_id)
        except Employee.DoesNotExist:
            messages.error(request, "Employee not found.")
            return render(request, 'preview_salary.html', {'employees': employees})

        # Final security: Managers can only preview their team members
        if not is_hr and employee.user.manager != request.user:
            messages.error(request, "You can only preview salary of employees in your team.")
            return redirect('employee:preview_salary')

        # Validate designation and base salary
        if not employee.designation or employee.designation.base_salary <= 0:
            messages.error(request, f"{employee.firstname} {employee.lastname} does not have a valid base salary assigned.")
            return render(request, 'preview_salary.html', {
                'employees': employees,
                'selected_employee': employee,
                'is_hr': is_hr
            })

        # Current month attendance
        current_month = date.today().month
        current_year = date.today().year

        attendance_records = Attendance.objects.filter(
            employee=employee,
            date__month=current_month,
            date__year=current_year
        )

        full_days = attendance_records.filter(work_status='Full Day').count()
        half_days = attendance_records.filter(work_status='Half Day').count()
        approved_leaves = Leave.objects.filter(
            employee=employee,
            status='Approved',
            start_date__month=current_month,
            start_date__year=current_year
        ).count()

        base_salary = float(employee.designation.base_salary)
        daily_salary = base_salary / 30  # assuming 30-day month

        gross_salary = (
            (full_days * daily_salary) +
            (half_days * daily_salary / 2) +
            (approved_leaves * daily_salary)
        )

        tax = gross_salary * 0.05  # 5% tax
        net_salary = gross_salary - tax

        salary_preview = {
            'full_days': full_days,
            'half_days': half_days,
            'approved_leaves': approved_leaves,
            'gross_salary': round(gross_salary, 2),
            'tax': round(tax, 2),
            'net_salary': round(net_salary, 2),
        }

        selected_employee = employee

        messages.success(request, f"Salary preview generated for {employee.firstname} {employee.lastname}")

    return render(request, 'preview_salary.html', {
        'employees': employees,
        'selected_employee': selected_employee,
        'salary_preview': salary_preview,
        'is_hr': is_hr,
        'current_month': date.today().strftime('%B %Y')
    })
# --------------------------------------------------------------
# CONFIRM GENERATE SALARY
# --------------------------------------------------------------
# --------------------------------------------------------------
# CONFIRM & SEND SALARY SLIP – HR: anyone, Manager: only their team
# --------------------------------------------------------------
# --------------------------------------------------------------
# CONFIRM & SEND SALARY SLIP – HR: anyone, Manager: only their team
# --------------------------------------------------------------
@login_required
def confirm_generate_salary(request, employee_id):
    if request.user.role not in ['HR', 'MANAGER']:
        messages.error(request, "You do not have permission to generate salary slips.")
        return redirect('employee:admin_dashboard')

    is_hr = request.user.role == 'HR'

    employee = get_object_or_404(Employee.objects.select_related('designation', 'user'), id=employee_id)

    # Security: Manager can only generate slip for their team
    if not is_hr and employee.user.manager != request.user:
        messages.error(request, "You can only generate salary slips for employees in your team.")
        return redirect('employee:preview_salary')

    if not employee.designation or employee.designation.base_salary <= 0:
        messages.error(request, f"{employee.firstname} {employee.lastname} does not have a valid base salary assigned.")
        return redirect('employee:preview_salary')

    today = date.today()
    current_month = today.strftime('%B %Y')  # e.g., "October 2025"

    attendance_records = Attendance.objects.filter(
        employee=employee,
        date__month=today.month,
        date__year=today.year
    )

    full_days = attendance_records.filter(work_status='Full Day').count()
    half_days = attendance_records.filter(work_status='Half Day').count()

    approved_leaves = Leave.objects.filter(
        employee=employee,
        status='Approved',
        start_date__month=today.month,
        start_date__year=today.year
    ).count()

    base_salary = float(employee.designation.base_salary)
    daily_salary = base_salary / 30

    gross_salary = (full_days * daily_salary) + (half_days * daily_salary / 2) + (approved_leaves * daily_salary)
    tax = gross_salary * 0.05
    net_salary = gross_salary - tax

    # Fixed: Now using current_month correctly
    subject = f"Salary Slip - {current_month}"
    message = f"""
Hello {employee.firstname} {employee.lastname},

Your salary summary for {current_month}:

→ Full Days Worked       : {full_days}
→ Half Days Worked       : {half_days}
→ Approved Leaves Taken  : {approved_leaves}

→ Base Salary            : ₹{base_salary:,.2f}
→ Gross Salary           : ₹{gross_salary:,.2f}
→ Tax Deducted (5%)      : ₹{tax:,.2f}
→ Net Salary             : ₹{net_salary:,.2f}

Thank you for your hard work!

Best regards,
{'HR Department' if is_hr else request.user.get_full_name() + ' (Your Manager)'}
    """.strip()

    try:
        send_mail(
            subject=subject,
            message=message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[employee.email],
            fail_silently=False,
        )
        messages.success(
            request,
            f"Salary slip successfully sent to {employee.firstname} {employee.lastname} ({employee.email})"
        )
    except Exception as e:
        messages.error(request, f"Failed to send salary slip: {str(e)}")

    return redirect('employee:preview_salary')
# --------------------------------------------------------------
# CALENDAR
# --------------------------------------------------------------
@login_required
def holiday_calendar(request):
    if not request.user.is_admin:
        return redirect('employee:login')
    
    year = int(request.GET.get('year', timezone.now().year))
    month = int(request.GET.get('month', timezone.now().month))
    
    cal = Calendar()
    month_days = cal.monthdayscalendar(year, month)
    holidays = Holiday.objects.filter(date__year=year, date__month=month)
    holiday_dates = [h.date.day for h in holidays]
    
    return render(request, 'calendar.html', {
        'year': year,
        'month': month,
        'month_days': month_days,
        'holiday_dates': holiday_dates,
        'holidays': holidays,
    })


# --------------------------------------------------------------
# TASK REPORT
# --------------------------------------------------------------
# --------------------------------------------------------------
# TASK REPORT – HR sees all, Managers see only their team
# --------------------------------------------------------------
@login_required
def task_report(request):
    if request.user.role not in ['HR', 'MANAGER']:
        messages.error(request, "Access denied.")
        return redirect('employee:login')

    is_hr = request.user.role == 'HR'

    if is_hr:
        tasks = Task.objects.select_related('employee', 'employee__designation').all()
    else:
        tasks = Task.objects.filter(employee__user__manager=request.user) \
                            .select_related('employee', 'employee__designation')

    task_status_summary = {
        'Pending': tasks.filter(status='Pending').count(),
        'In Progress': tasks.filter(status='In Progress').count(),
        'Completed': tasks.filter(status='Completed').count(),
    }

    return render(request, 'task_report.html', {
        'tasks': tasks,
        'task_status_summary': task_status_summary,
        'is_hr': is_hr,
    })

# --------------------------------------------------------------
# GENERATE TASK PDF
# --------------------------------------------------------------
# --------------------------------------------------------------
# GENERATE TASK PDF – Only HR or Manager of the employee
# --------------------------------------------------------------
@login_required
def generate_task_pdf(request, task_id):
    if request.user.role not in ['HR', 'MANAGER']:
        messages.error(request, "You do not have permission to download task reports.")
        return redirect('employee:login')

    task = get_object_or_404(Task, id=task_id, status='Completed')
    employee_user = task.employee.user
    is_hr = request.user.role == 'HR'

    # Security: Manager can only download tasks of their team
    if not is_hr and employee_user.manager != request.user:
        messages.error(request, "You can only download task reports for your team members.")
        return redirect('employee:task_report')

    response = HttpResponse(content_type='application/pdf')
    safe_name = "".join(c for c in task.task_name if c.isalnum() or c in " -_")
    response['Content-Disposition'] = f'attachment; filename="Task_Report_{safe_name}_{task.employee.firstname}.pdf"'

    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter)
    elements = []
    styles = getSampleStyleSheet()

    title_style = ParagraphStyle(name='Title', fontSize=24, textColor=colors.HexColor('#1a2533'), alignment=1)
    heading_style = ParagraphStyle(name='Heading2', fontSize=18, textColor=colors.HexColor('#1a2533'))
    normal_style = ParagraphStyle(name='Normal', fontSize=14, leading=18)

    elements.append(Paragraph(f"Task Completion Report", title_style))
    elements.append(Spacer(1, 20))
    
    elements.append(Paragraph("Employee Details", heading_style))
    elements.append(Paragraph(f"Name: {task.employee.firstname} {task.employee.lastname}", normal_style))
    elements.append(Paragraph(f"Designation: {task.employee.designation.designation_name}", normal_style))
    elements.append(Paragraph(f"Base Salary: ₹{task.employee.designation.base_salary:,.2f}", normal_style))
    elements.append(Spacer(1, 20))

    elements.append(Paragraph("Task Details", heading_style))
    elements.append(Paragraph(f"Task Name: {task.task_name}", normal_style))
    elements.append(Paragraph(f"Description: {task.task_desc}", normal_style))
    elements.append(Paragraph(f"Status: <font color='green'><b>{task.status}</b></font>", normal_style))
    elements.append(Paragraph(f"Progress: {task.progress}%", normal_style))
    elements.append(Paragraph(f"Start Date: {task.start_date}", normal_style))
    elements.append(Paragraph(f"Due Date: {task.due_date}", normal_style))
    elements.append(Paragraph(f"Completed On: {task.subtasks.filter(completed=True).first().date_completed if hasattr(task.subtasks.first(), 'date_completed') else 'N/A'}", normal_style))
    elements.append(Spacer(1, 20))

    subtasks = task.subtasks.all()
    if subtasks.exists():
        elements.append(Paragraph("Subtasks Completed", heading_style))
        data = [["#", "Subtask Name", "Status"]]
        for i, s in enumerate(subtasks, 1):
            status = "Yes" if s.completed else "No"
            data.append([i, s.name, status])
        table = Table(data, colWidths=[50, 350, 100])
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#d3d3d3')),
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ]))
        elements.append(table)

    elements.append(Spacer(1, 30))
    elements.append(Paragraph(f"Report generated by: {request.user.get_full_name() or request.user.username}", normal_style))
    elements.append(Paragraph(f"Date: {date.today().strftime('%d %B %Y')}", normal_style))

    doc.build(elements)
    response.write(buffer.getvalue())
    buffer.close()
    return response
# --------------------------------------------------------------
# SALARY GENERATION + PDF + EMAIL + NO DUPLICATES
# --------------------------------------------------------------
# --------------------------------------------------------------
# GENERATE SALARY + PDF + EMAIL – HR: all, Manager: only team
# --------------------------------------------------------------
@login_required
def generate_salary(request):
    if request.user.role not in ['HR', 'MANAGER']:
        messages.error(request, "You do not have permission to generate salaries.")
        return redirect('employee:admin_dashboard')

    is_hr = request.user.role == 'HR'

    # Filter employees based on role
    if is_hr:
        employees = Employee.objects.select_related('designation').all()
    else:
        employees = Employee.objects.filter(user__manager=request.user).select_related('designation')

    months = [
        {'value': i, 'name': calendar.month_name[i]} for i in range(1, 13)
    ]

    current_month = timezone.now().month
    current_year = timezone.now().year

    if request.method == 'POST':
        try:
            employee_id = request.POST.get('employee')
            month = int(request.POST.get('month'))
            year = int(request.POST.get('year'))

            if not employee_id:
                messages.error(request, "Please select an employee.")
                return redirect('employee:generate_salary')

            employee = get_object_or_404(Employee, id=employee_id)

            # Final security check for Managers
            if not is_hr and employee.user.manager != request.user:
                messages.error(request, "You can only generate salary for your team members.")
                return redirect('employee:generate_salary')

            # Prevent duplicate salary
            if Salary.objects.filter(employee=employee, month=month, year=year).exists():
                messages.error(request, f"Salary already generated for {employee.firstname} in {month}/{year}.")
                return redirect('employee:generate_salary')

            # Calculate salary
            attendances = Attendance.objects.filter(employee=employee, date__month=month, date__year=year)
            full_days = attendances.filter(work_status='Full Day').count()
            half_days = attendances.filter(work_status='Half Day').count()
            days_worked = full_days + (half_days * 0.5)

            basic_salary = float(employee.designation.base_salary)
            per_day = basic_salary / 30
            gross = per_day * days_worked
            tds = gross * 0.1
            prof_tax = 200 if gross > 15000 else 0
            final_salary = gross - tds - prof_tax

            salary = Salary.objects.create(
                employee=employee,
                month=month,
                year=year,
                basic_salary=basic_salary,
                days_worked=round(days_worked, 1),
                tds=round(tds, 2),
                professional_tax=prof_tax,
                final_salary=round(final_salary, 2)
            )

            # Generate PDF + Send Email
            try:
                pdf = generate_salary_pdf_buffer(salary)
                html_message = render_to_string('salary_email.html', {
                    'employee': employee,
                    'salary': salary,
                    'gross': gross,
                })

                email = EmailMessage(
                    subject=f"Salary Slip - {calendar.month_name[month]} {year}",
                    body=html_message,
                    from_email=settings.EMAIL_HOST_USER,
                    to=[employee.email],
                )
                email.content_subtype = "html"
                email.attach(f"Salary_Slip_{employee.firstname}_{month}_{year}.pdf", pdf, 'application/pdf')
                email.send()

                messages.success(request, f"Salary generated and emailed to {employee.email}")
            except Exception as e:
                messages.warning(request, f"Salary saved but email failed: {str(e)}")

            return redirect('employee:admin_dashboard')

        except Exception as e:
            messages.error(request, f"Error generating salary: {str(e)}")
            return redirect('employee:generate_salary')

    return render(request, 'generate_salary.html', {
        'employees': employees,
        'months': months,
        'current_month': current_month,
        'current_year': current_year,
        'is_hr': is_hr,
    })

# --------------------------------------------------------------
# PDF GENERATOR (REUSABLE)
# --------------------------------------------------------------
def generate_salary_pdf_buffer(salary):
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter)
    elements = []
    styles = getSampleStyleSheet()

    elements.append(Paragraph("Salary Slip", styles['Title']))
    elements.append(Spacer(1, 12))

    emp = salary.employee
    data = [
        ["Employee", f"{emp.firstname} {emp.lastname}"],
        ["Designation", emp.designation.designation_name],
        ["Month / Year", f"{salary.month}/{salary.year}"],
    ]
    t = Table(data, colWidths=[200, 300])
    t.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (0, -1), colors.HexColor('#f0f0f0')),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
    ]))
    elements.append(t)
    elements.append(Spacer(1, 20))

    gross = (salary.basic_salary / 30) * salary.days_worked
    breakdown = [
        ["Description", "Amount (₹)"],
        ["Basic Salary", f"{salary.basic_salary:,.2f}"],
        ["Days Worked", f"{salary.days_worked}"],
        ["Gross Salary", f"{gross:,.2f}"],
        ["TDS (10%)", f"{salary.tds:,.2f}"],
        ["Professional Tax", f"{salary.professional_tax:,.2f}"],
        ["", ""],
        ["Net Salary", f"<b>{salary.final_salary:,.2f}</b>"],
    ]
    bt = Table(breakdown, colWidths=[300, 200])
    bt.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#d3d3d3')),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.black),
        ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, -1), (-1, -1), 12),
    ]))
    elements.append(bt)

    doc.build(elements)
    pdf = buffer.getvalue()
    buffer.close()
    return pdf


# --------------------------------------------------------------
# PDF DOWNLOAD (Admin Only)
# --------------------------------------------------------------
# DOWNLOAD SALARY SLIP PDF – HR: any, Manager: only their team
# --------------------------------------------------------------
@login_required
def salary_slip_pdf(request, salary_id):
    # Only HR and Managers can download salary slips
    if request.user.role not in ['HR', 'MANAGER']:
        messages.error(request, "You do not have permission to download salary slips.")
        return redirect('employee:admin_dashboard')

    is_hr = request.user.role == 'HR'

    salary = get_object_or_404(Salary.objects.select_related('employee', 'employee__user'), id=salary_id)

    # Security: Manager can only download salary slips of their team members
    if not is_hr and salary.employee.user.manager != request.user:
        messages.error(request, "You can only download salary slips for employees in your team.")
        return redirect('employee:admin_dashboard')

    # Generate PDF
    try:
        pdf = generate_salary_pdf_buffer(salary)
    except Exception as e:
        messages.error(request, f"Error generating PDF: {str(e)}")
        return redirect('employee:admin_dashboard')

    # Safe filename
    safe_name = f"{salary.employee.firstname}_{salary.employee.lastname}".replace(" ", "_")
    month_year = f"{salary.month:02d}_{salary.year}"

    response = HttpResponse(pdf, content_type='application/pdf')
    response['Content-Disposition'] = (
        f'attachment; filename="Salary_Slip_{safe_name}_{month_year}.pdf"'
    )
    response['Content-Transfer-Encoding'] = 'binary'

    return response

@login_required
def give_feedback(request):
    if request.user.role not in ['HR', 'MANAGER']:
        messages.error(request, "You don't have permission to give feedback.")
        return redirect('employee:admin_dashboard')

    if request.method == 'POST':
        employee_id = request.POST['employee_id']
        feedback_text = request.POST['feedback']
        rating = request.POST['rating']

        employee = get_object_or_404(Employee, id=employee_id)

        # Manager can only give feedback to their team
        if request.user.role == 'MANAGER' and employee.user.manager != request.user:
            messages.error(request, "You can only give feedback to your team members.")
        else:
            Feedback.objects.create(
                employee=employee,
                feedback_text=feedback_text,
                rating=rating,
                given_by=request.user
            )
            messages.success(request, f"Feedback sent to {employee.firstname} {employee.lastname}!")
    
    return redirect('employee:admin_dashboard')


@login_required
def holiday_calendar(request):
    year = int(request.GET.get('year', datetime.now().year))
    
    # PRE-LOADED MAJOR INDIAN HOLIDAYS (2025-2029) - ACCURATE DATES
    pre_loaded_holidays = {
        2025: {
            (1, 26): "Republic Day",
            (2, 26): "Maha Shivratri",
            (3, 14): "Holi",
            (4, 18): "Good Friday",
            (8, 15): "Independence Day",
            (10, 2): "Gandhi Jayanti",
            (10, 20): "Diwali",
            (12, 25): "Christmas",
        },
        2026: {
            (1, 26): "Republic Day",
            (3, 4): "Holi",
            (4, 3): "Good Friday",
            (8, 15): "Independence Day",
            (10, 2): "Gandhi Jayanti",
            (11, 8): "Diwali",
            (12, 25): "Christmas",
        },
        2027: {
            (1, 26): "Republic Day",
            (3, 24): "Holi",
            (3, 26): "Good Friday",
            (8, 15): "Independence Day",
            (10, 2): "Gandhi Jayanti",
            (10, 28): "Diwali",
            (12, 25): "Christmas",
        },
        2028: {
            (1, 26): "Republic Day",
            (3, 13): "Holi",
            (4, 14): "Good Friday",
            (8, 15): "Independence Day",
            (10, 2): "Gandhi Jayanti",
            (10, 17): "Diwali",
            (12, 25): "Christmas",
        },
        2029: {
            (1, 26): "Republic Day",
            (3, 2): "Holi",
            (3, 30): "Good Friday",
            (8, 15): "Independence Day",
            (10, 2): "Gandhi Jayanti",
            (11, 5): "Diwali",
            (12, 25): "Christmas",
        },
    }
    
    # Get pre-loaded for current year
       # Build nested dict: { month: { day: "Name", ... }, ... }
    holiday_dict = {}
    pre_loaded = pre_loaded_holidays.get(year, {})
    for (month, day), name in pre_loaded.items():
        if month not in holiday_dict:
            holiday_dict[month] = {}
        holiday_dict[month][day] = name

    # Add/override from database
    db_holidays = Holiday.objects.filter(date__year=year)
    for h in db_holidays:
        month = h.date.month
        day = h.date.day
        if month not in holiday_dict:
            holiday_dict[month] = {}
        holiday_dict[month][day] = h.name  # Supports multiples (last wins if duplicate)
    
    # Generate calendar (Sunday first)
    import calendar
    cal = calendar.Calendar(firstweekday=6)
    
    months = []
    for month in range(1, 13):
        month_days = cal.monthdayscalendar(year, month)
        months.append({
            'name': calendar.month_name[month],
            'days': month_days,
            'month_num': month,
        })
    
    context = {
        'year': year,
        'months': months,
        'holiday_dict': holiday_dict,
        'prev_year': year - 1,
        'next_year': year + 1,
         # Make the function available in template
        
    }
    return render(request, 'holiday_calendar.html', context)