from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import LoginView
from django.db import transaction
from django.shortcuts import redirect, render
from django.urls import reverse_lazy
from django.views.generic import CreateView

from organizations.models import Membership

from .access import user_has_admin_access, user_is_teacher
from .forms import EmailAuthenticationForm, SignUpForm


class SignInView(LoginView):
    template_name = "registration/login.html"
    authentication_form = EmailAuthenticationForm


class SignUpView(CreateView):
    form_class = SignUpForm
    template_name = "registration/signup.html"
    success_url = reverse_lazy("accounts:login")
    signup_role = None

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["signup_role"] = self.signup_role
        return kwargs

    def form_valid(self, form):
        with transaction.atomic():
            self.object = form.save()
            role = form.cleaned_data["role"]
            membership_role = Membership.Role.TEACHER if role == SignUpForm.Role.TEACHER else Membership.Role.STUDENT
            Membership.objects.create(
                organization=form.cleaned_data["organization"],
                user=self.object,
                role=membership_role,
            )
        messages.success(self.request, "Account created. Sign in to start learning with Aiducator.")
        return redirect(self.get_success_url())


class TeacherSignUpView(SignUpView):
    signup_role = SignUpForm.Role.TEACHER


class StudentSignUpView(SignUpView):
    signup_role = SignUpForm.Role.STUDENT


def dashboard(request):
    if not request.user.is_authenticated:
        return redirect("accounts:login")
    if user_has_admin_access(request.user):
        return redirect("dashboard:administrator-dashboard")
    if user_is_teacher(request.user):
        return redirect("dashboard:teacher-dashboard")
    return redirect("dashboard:student-dashboard")


@login_required
def profile(request):
    memberships = request.user.memberships.select_related("organization").order_by("organization__name")
    return render(request, "accounts/profile.html", {"memberships": memberships})
