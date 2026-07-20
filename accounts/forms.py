from django import forms
from django.contrib.auth import authenticate
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm

from organizations.models import Organization

from .models import User


class SignUpForm(UserCreationForm):
    class Role:
        STUDENT = "student"
        TEACHER = "teacher"

        choices = (
            (STUDENT, "Student"),
            (TEACHER, "Teacher"),
        )

    role = forms.ChoiceField(
        choices=Role.choices,
        initial=Role.STUDENT,
        required=False,
        label="I am signing up as a",
    )
    organization = forms.ModelChoiceField(
        label="School or Organization name",
        queryset=Organization.objects.none(),
        empty_label="Select your school or organization",
        help_text="Choose the school, organization, or classroom you are joining.",
    )

    def __init__(self, *args, signup_role=None, **kwargs):
        self.signup_role = signup_role
        super().__init__(*args, **kwargs)
        self.fields["organization"].queryset = Organization.objects.order_by("name")
        self.fields["first_name"].widget.attrs["autofocus"] = "autofocus"
        if signup_role:
            self.fields["role"].initial = signup_role
            self.fields["role"].widget = forms.HiddenInput()

    class Meta:
        model = User
        fields = ("first_name", "last_name", "email", "role", "organization")

    def clean_role(self):
        if self.signup_role:
            return self.signup_role
        return self.cleaned_data.get("role") or self.Role.STUDENT

    def clean_email(self):
        return self.cleaned_data["email"].lower().strip()


class EmailAuthenticationForm(AuthenticationForm):
    username = forms.EmailField(label="Email address")

    def clean(self):
        email = self.cleaned_data.get("username")
        password = self.cleaned_data.get("password")
        if email and password:
            self.user_cache = authenticate(self.request, email=email, password=password)
            if self.user_cache is None:
                raise self.get_invalid_login_error()
            self.confirm_login_allowed(self.user_cache)
        return self.cleaned_data
