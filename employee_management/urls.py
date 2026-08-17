# employee_management/urls.py
from django.contrib import admin
from django.urls import path, include
from django.shortcuts import redirect

def root_redirect(request):
    """Redirect / → /login/"""
    return redirect('employee:login')

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('employee.urls')),
    # Catch the empty path and send the visitor to login
    path('', root_redirect, name='root'),
]