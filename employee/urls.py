from django.urls import path
from . import views

app_name = 'employee'

urlpatterns = [
    path('login/', views.user_login, name='login'),
    path('logout/', views.user_logout, name='logout'),
    path('admin_dashboard/', views.admin_dashboard, name='admin_dashboard'),
    path('get-designations/', views.get_designations, name='get_designations'),
    path('get-team/', views.get_team, name='get_team'),

    # path('departments/', views.manage_departments, name='manage_departments'),
    path('department/add/', views.add_department, name='add_department'),
    path('department/edit/<int:dept_id>/', views.edit_department, name='edit_department'),
    path('department/delete/<int:dept_id>/', views.delete_department, name='delete_department'),
    
    # FIXED: Removed <int:employee_id> — employee knows who they are via request.user
    path('employee_dashboard/', views.employee_dashboard, name='employee_dashboard'),
    
    path('add_employee/', views.add_employee, name='add_employee'),
    path('add_employee_success/<str:firstname>/<str:lastname>/', views.add_employee_success, name='add_employee_success'),
    path('edit_employee/<int:employee_id>/', views.edit_employee, name='edit_employee'),
    path('delete_employee/<int:employee_id>/', views.delete_employee, name='delete_employee'),

    # Leave management
    path('leave-request/', views.leave_request, name='leave_request'),
    path('approve_leave/<int:leave_id>/', views.approve_leave, name='approve_leave'),
    path('partial_approve_leave/<int:leave_id>/', views.partial_approve_leave, name='partial_approve_leave'),
    path('reject_leave/<int:leave_id>/', views.reject_leave, name='reject_leave'),

    # Tasks and designations
    path('assign_task/', views.assign_task, name='assign_task'),
    path('update_task/<int:task_id>/', views.update_task, name='update_task'),
    path('delete_task/<int:task_id>/', views.delete_task, name='delete_task'),
    path('update_employee_task/<int:task_id>/', views.update_employee_task, name='update_employee_task'),
    path('attendance_report/<int:employee_id>/', views.attendance_report, name='attendance_report'),
    # path('designations/', views.manage_designations, name='manage_designations'),
    path('designation/add/', views.add_designation, name='add_designation'),
    path('designation/edit/<int:designation_id>/', views.edit_designation, name='edit_designation'),
    path('designation/delete/<int:designation_id>/', views.delete_designation, name='delete_designation'),
    # Calendar & reports
    path('calendar/', views.holiday_calendar, name='calendar'),
    path('task_report/', views.task_report, name='task_report'),
    path('generate_task_pdf/<int:task_id>/', views.generate_task_pdf, name='generate_task_pdf'),

    # Salary Generation
    path('preview-salary/', views.preview_salary, name='preview_salary'),
    path('confirm-generate-salary/<int:employee_id>/', views.confirm_generate_salary, name='confirm_generate_salary'),
    #Feedback
    path('give-feedback/', views.give_feedback, name='give_feedback'),

    path('calendar/', views.holiday_calendar, name='holiday_calendar'),
]