# employee_management
A Django-based Employee Management System for managing employee records, attendance, leave applications, and employee statistics.

# Employee Management System

A comprehensive web-based **Employee Management System** developed using **Python and Django** to simplify and manage various employee-related activities through a centralized platform.

## 📌 Project Overview

The Employee Management System is designed to help organizations efficiently manage employee information, attendance, leave requests, tasks, departments, designations, holidays, and salary-related activities.

The system provides separate functionality for administrators and employees, allowing HR/admin users to manage employee records and allowing employees to access their personal information, attendance, leave requests, tasks, and other services.

## ✨ Key Features

### 👨‍💼 Employee Management

* Add new employees
* Edit and update employee information
* Manage employee profiles
* Manage departments and designations
* View employee records

### 📅 Attendance Management

* Track employee attendance
* Maintain attendance records
* Generate attendance reports
* View attendance-related statistics

### 🏖️ Leave Management

* Employees can submit leave requests
* Admin can approve or reject leave requests
* Track leave status
* Manage leave-related records

### 💰 Salary Management

* Generate employee salary details
* Generate salary slips
* Preview salary information
* Salary-related email functionality

### 📋 Task Management

* Assign tasks to employees
* Update task status
* Track employee tasks
* Generate task-related documents/reports

### 📊 Dashboard & Statistics

* Admin dashboard
* Employee dashboard
* Employee and attendance statistics
* Overview of important employee information

### 🗓️ Holiday Management

* Holiday calendar
* Manage organizational holidays
* Display holidays to employees

### 🔐 Authentication & Access Control

* User login
* Employee and admin functionality
* Role-based access to different features

### 📝 Feedback

* Employee feedback functionality
* Feedback management

## 🛠️ Technology Stack

| Technology   | Usage                     |
| ------------ | ------------------------- |
| Python       | Backend programming       |
| Django       | Web framework             |
| HTML         | Frontend structure        |
| CSS          | Styling                   |
| JavaScript   | Client-side functionality |
| SQLite/MySQL | Database                  |
| Bootstrap    | UI components             |
| Git & GitHub | Version control           |

## 📂 Project Structure

```text
employee-management-system/
│
├── employee/
│   ├── migrations/
│   ├── static/
│   ├── templates/
│   ├── templatetags/
│   ├── admin.py
│   ├── models.py
│   ├── urls.py
│   ├── views.py
│   └── ...
│
├── employee_management/
│   ├── settings.py
│   ├── urls.py
│   ├── asgi.py
│   └── wsgi.py
│
├── manage.py
├── requirements.txt
└── README.md
```

## ⚙️ Installation & Setup

### 1. Clone the repository

```bash
git clone https://github.com/YOUR-USERNAME/employee-management-system.git
cd employee-management-system
```

### 2. Create a virtual environment

```bash
python -m venv venv
```

### 3. Activate the virtual environment

**Windows:**

```bash
venv\Scripts\activate
```

### 4. Install dependencies

```bash
pip install -r requirements.txt
```

### 5. Apply migrations

```bash
python manage.py migrate
```

### 6. Run the development server

```bash
python manage.py runserver
```

Open the application in your browser at:

```text
http://127.0.0.1:8000/
```

## 🎯 Project Objectives

* Automate employee management processes
* Reduce manual record keeping
* Simplify attendance and leave tracking
* Provide organized salary and task management
* Provide useful employee statistics and reports
* Improve accessibility of employee-related information

## 📚 Skills Demonstrated

Through this project, I gained practical experience in:

* Python programming
* Django framework
* MVC/MVT architecture
* Database management
* CRUD operations
* Authentication and access control
* HTML/CSS/JavaScript
* Backend development
* Template integration
* Database migrations
* Git and GitHub

## 👤 Author

**Kashish Jobaliya**

This project was developed as an academic project to demonstrate practical knowledge of **Django, Python, database management, and web application development**.

