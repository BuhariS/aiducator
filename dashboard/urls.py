from django.urls import path

from courses.views import student_dashboard, teacher_dashboard

app_name = "dashboard"

urlpatterns = [
    path("student/", student_dashboard, name="student-dashboard"),
    path("teacher/", teacher_dashboard, name="teacher-dashboard"),
]
