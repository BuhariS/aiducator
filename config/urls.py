from django.contrib import admin
from django.urls import include, path
from django.views.generic import RedirectView


urlpatterns = [
    path("", RedirectView.as_view(pattern_name="courses:catalog", permanent=False)),
    path("admin/", admin.site.urls),
    path("accounts/", include("accounts.urls")),
    path("dashboard/", include("dashboard.urls")),
    path("courses/", include("courses.urls")),
    path("teacher/courses/", include("teacher_courses.urls")),
    path("assessments/", include("assessments.urls")),
]
