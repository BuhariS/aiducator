import uuid

from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import LoginView
from django.db import transaction
from django.shortcuts import redirect, render
from django.urls import reverse_lazy
from django.utils.text import slugify
from django.views.generic import CreateView

from organizations.models import Membership, Organization

from .access import user_has_admin_access, user_is_teacher
from .forms import EmailAuthenticationForm, SignUpForm


class SignInView(LoginView):
    template_name = "registration/login.html"
    authentication_form = EmailAuthenticationForm


class SignUpView(CreateView):
    form_class = SignUpForm
    template_name = "registration/signup.html"
    success_url = reverse_lazy("accounts:dashboard")
    signup_role = None

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["signup_role"] = self.signup_role
        return kwargs

    def form_valid(self, form):
        with transaction.atomic():
            self.object = form.save()
            display_name = self.object.get_full_name() or self.object.email.split("@", 1)[0]
            role = form.cleaned_data["role"]
            if role == SignUpForm.Role.TEACHER:
                organization_name = form.cleaned_data["organization_name"].strip()
                membership_role = Membership.Role.TEACHER
            else:
                organization_name = f"{display_name}'s Learning Space"
                membership_role = Membership.Role.STUDENT
            organization_slug = f"{slugify(organization_name)[:180]}-{uuid.uuid4().hex[:8]}"
            organization = Organization.objects.create(name=organization_name, slug=organization_slug)
            Membership.objects.create(
                organization=organization,
                user=self.object,
                role=membership_role,
            )
        login(self.request, self.object)
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
    return render(request, "accounts/profile.html")
