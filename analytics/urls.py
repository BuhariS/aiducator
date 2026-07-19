from django.urls import path

from .views import (
    administrator_analytics_view,
    record_lesson_time_view,
    teacher_ai_analysis_view,
    teacher_analytics_view,
)

app_name = "analytics"

urlpatterns = [
    path("teacher/", teacher_analytics_view, name="teacher"),
    path("teacher/analyze/", teacher_ai_analysis_view, name="teacher-analyze"),
    path("administrator/", administrator_analytics_view, name="administrator"),
    path("lessons/<uuid:lesson_id>/time/", record_lesson_time_view, name="lesson-time"),
]
