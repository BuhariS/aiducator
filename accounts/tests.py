from django.core import mail
from django.test import TestCase
from django.urls import reverse
from django.test import override_settings

from organizations.models import Membership

from .models import User


class AuthenticationTests(TestCase):
    def test_user_can_sign_up_and_continue_to_sign_in(self):
        response = self.client.post(
            reverse("accounts:signup"),
            {
                "first_name": "Ada",
                "last_name": "Lovelace",
                "email": "ada@example.com",
                "role": "student",
                "password1": "StrongPass123!",
                "password2": "StrongPass123!",
            },
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse("accounts:login"))
        self.assertTrue(User.objects.filter(email="ada@example.com").exists())
        user = User.objects.get(email="ada@example.com")
        self.assertTrue(user.memberships.filter(role=Membership.Role.STUDENT).exists())

    def test_user_can_sign_up_as_a_teacher(self):
        response = self.client.post(
            reverse("accounts:signup-teacher"),
            {
                "first_name": "Grace",
                "last_name": "Hopper",
                "email": "grace@example.com",
                "organization_name": "Lagos Coding School",
                "password1": "StrongPass123!",
                "password2": "StrongPass123!",
            },
        )
        self.assertEqual(response.status_code, 302)
        user = User.objects.get(email="grace@example.com")
        membership = user.memberships.get()
        self.assertEqual(membership.role, Membership.Role.TEACHER)
        self.assertEqual(membership.organization.name, "Lagos Coding School")
        self.assertEqual(response.url, reverse("accounts:login"))

    def test_default_signup_selects_student_and_focuses_first_name(self):
        response = self.client.get(reverse("accounts:signup"))

        self.assertEqual(response.context["form"].fields["role"].initial, "student")
        self.assertEqual(response.context["form"].fields["first_name"].widget.attrs["autofocus"], "autofocus")

    def test_teacher_signup_requires_an_organization_name(self):
        response = self.client.post(
            reverse("accounts:signup-teacher"),
            {
                "first_name": "Grace",
                "last_name": "Hopper",
                "email": "grace@example.com",
                "password1": "StrongPass123!",
                "password2": "StrongPass123!",
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Enter your school or classroom name to continue.")
        self.assertFalse(User.objects.filter(email="grace@example.com").exists())

    def test_user_can_sign_in_with_email(self):
        User.objects.create_user(email="learner@example.com", password="StrongPass123!")
        response = self.client.post(
            reverse("accounts:login"),
            {"username": "learner@example.com", "password": "StrongPass123!"},
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse("accounts:dashboard"))

    @override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
    def test_user_can_request_a_password_reset(self):
        User.objects.create_user(email="recover@example.com", password="StrongPass123!")
        response = self.client.post(
            reverse("accounts:password-reset"),
            {"email": "recover@example.com"},
        )
        self.assertRedirects(response, reverse("accounts:password-reset-done"))
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("/accounts/reset/", mail.outbox[0].body)

    def test_authenticated_session_security_defaults_are_enabled(self):
        from django.conf import settings

        self.assertTrue(settings.SESSION_COOKIE_HTTPONLY)
        self.assertEqual(settings.SESSION_COOKIE_SAMESITE, "Lax")
