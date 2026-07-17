from django.contrib.auth.views import LogoutView
from django.urls import path

from .views import SignInView, SignUpView, StudentSignUpView, TeacherSignUpView, dashboard, profile

app_name = "accounts"

urlpatterns = [
    path("login/", SignInView.as_view(), name="login"),
    path("signup/", SignUpView.as_view(), name="signup"),
    path("signup/teacher/", TeacherSignUpView.as_view(), name="signup-teacher"),
    path("signup/student/", StudentSignUpView.as_view(), name="signup-student"),
    path("logout/", LogoutView.as_view(), name="logout"),
    path("dashboard/", dashboard, name="dashboard"),
    path("profile/", profile, name="profile"),
]
