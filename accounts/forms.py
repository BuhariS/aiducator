from django import forms
from django.contrib.auth import authenticate
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm

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
    organization_name = forms.CharField(
        label="School or Organization name",
        max_length=180,
        required=False,
        help_text="Teachers create a workspace for the school or organization they represent.",
    )

    def __init__(self, *args, signup_role=None, **kwargs):
        self.signup_role = signup_role
        super().__init__(*args, **kwargs)
        self.fields["first_name"].widget.attrs["autofocus"] = "autofocus"
        if signup_role:
            self.fields["role"].initial = signup_role
            self.fields["role"].widget = forms.HiddenInput()
            if signup_role == self.Role.STUDENT:
                self.fields.pop("organization_name")
            else:
                self.fields["organization_name"].required = True

    class Meta:
        model = User
        fields = ("first_name", "last_name", "email", "role", "organization_name")

    def clean_role(self):
        if self.signup_role:
            return self.signup_role
        return self.cleaned_data.get("role") or self.Role.STUDENT

    def clean_email(self):
        return self.cleaned_data["email"].lower().strip()

    def clean_organization_name(self):
        organization_name = self.cleaned_data.get("organization_name", "").strip()
        role = self.cleaned_data.get("role") or self.signup_role
        if role == self.Role.TEACHER and not organization_name:
            raise forms.ValidationError("Enter your school or organization name.")
        return organization_name


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
