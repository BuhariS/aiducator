from django.urls import path

from courses.views import student_dashboard, teacher_dashboard

from .views import administrator_dashboard

app_name = "dashboard"

urlpatterns = [
    path("administrator/", administrator_dashboard, name="administrator-dashboard"),
    path("student/", student_dashboard, name="student-dashboard"),
    path("teacher/", teacher_dashboard, name="teacher-dashboard"),
]
