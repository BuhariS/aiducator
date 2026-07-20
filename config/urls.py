from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path
from django.views.generic import RedirectView


urlpatterns = [
    path("", RedirectView.as_view(pattern_name="courses:catalog", permanent=False)),
    path("admin/", admin.site.urls),
    path("accounts/", include("accounts.urls")),
    path("dashboard/", include("dashboard.urls")),
    path("analytics/", include("analytics.urls")),
    path("notifications/", include("notifications.urls")),
    path("courses/", include("courses.urls")),
    path("teacher/courses/", include("teacher_courses.urls")),
    path("assessments/", include("assessments.urls")),
]

if settings.DEBUG and settings.STORAGE_BACKEND == "filesystem":
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
