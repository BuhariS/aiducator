from django.test import TestCase
from django.urls import reverse

from accounts.models import User
from organizations.models import Membership, Organization


class DashboardPermissionTests(TestCase):
    def setUp(self):
        self.organization = Organization.objects.create(name="Admin School", slug="admin-school")
        self.admin = User.objects.create_user(email="admin@example.com", password="StrongPass123!")
        self.teacher = User.objects.create_user(email="teacher@example.com", password="StrongPass123!")
        self.student = User.objects.create_user(email="student@example.com", password="StrongPass123!")
        Membership.objects.create(
            organization=self.organization,
            user=self.admin,
            role=Membership.Role.ADMIN,
        )
        Membership.objects.create(
            organization=self.organization,
            user=self.teacher,
            role=Membership.Role.TEACHER,
        )
        Membership.objects.create(
            organization=self.organization,
            user=self.student,
            role=Membership.Role.STUDENT,
        )

    def test_administrator_sees_only_owned_organizations(self):
        self.client.force_login(self.admin)
        response = self.client.get(reverse("dashboard:administrator-dashboard"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Admin School")

    def test_student_cannot_open_administrator_dashboard(self):
        self.client.force_login(self.student)
        response = self.client.get(reverse("dashboard:administrator-dashboard"))
        self.assertEqual(response.status_code, 403)

    def test_student_cannot_open_teacher_dashboard(self):
        self.client.force_login(self.student)
        response = self.client.get(reverse("dashboard:teacher-dashboard"))
        self.assertEqual(response.status_code, 403)

    def test_account_dashboard_routes_admin_to_administrator_dashboard(self):
        self.client.force_login(self.admin)
        response = self.client.get(reverse("accounts:dashboard"))
        self.assertRedirects(response, reverse("dashboard:administrator-dashboard"))
