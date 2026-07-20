from django.urls import path

from .views import inbox

app_name = "notifications"

urlpatterns = [path("", inbox, name="inbox")]
