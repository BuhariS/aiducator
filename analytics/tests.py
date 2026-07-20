from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from django.urls import reverse

from accounts.models import User
from courses.models import Course, CourseVersion, LessonVersion, Module
from enrollments.models import CourseCompletion, Enrollment, LessonProgress
from organizations.models import Membership, Organization

from .models import LessonTimeEvent
from .services import teacher_analytics, teacher_course_metrics


class AnalyticsAccessTests(TestCase):
    def setUp(self):
        self.organization = Organization.objects.create(
            name="Analytics School", slug="analytics-school"
        )
        self.teacher = User.objects.create_user(
            email="teacher@analytics.test", password="StrongPass123!"
        )
        self.student = User.objects.create_user(
            email="student@analytics.test", password="StrongPass123!"
        )
        self.admin = User.objects.create_user(
            email="admin@analytics.test", password="StrongPass123!"
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
        Membership.objects.create(
            organization=self.organization,
            user=self.admin,
            role=Membership.Role.ADMIN,
        )
        self.course = Course.objects.create(
            organization=self.organization,
            created_by=self.teacher,
            title="Python Analytics",
            slug="python-analytics",
        )
        self.version = CourseVersion.objects.create(course=self.course, version_number=1)
        self.module = Module.objects.create(
            course_version=self.version, title="Foundations", position=1
        )
        self.lesson = LessonVersion.objects.create(
            module=self.module,
            title="Variables",
            content="Store values in names.",
            position=1,
        )
        self.enrollment = Enrollment.objects.create(
            course=self.course,
            course_version=self.version,
            student=self.student,
        )

    def test_student_can_record_owned_lesson_time(self):
        self.client.force_login(self.student)
        response = self.client.post(
            reverse("analytics:lesson-time", args=[self.lesson.id]),
            {"duration_seconds": "120"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(LessonTimeEvent.objects.get().duration_seconds, 120)

    def test_invalid_lesson_time_is_rejected(self):
        self.client.force_login(self.student)
        response = self.client.post(
            reverse("analytics:lesson-time", args=[self.lesson.id]),
            {"duration_seconds": "0"},
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(LessonTimeEvent.objects.count(), 0)

    def test_teacher_and_admin_analytics_are_role_protected(self):
        self.client.force_login(self.teacher)
        teacher_response = self.client.get(reverse("analytics:teacher"))
        self.assertEqual(teacher_response.status_code, 200)
        self.assertContains(teacher_response, "How each metric is evaluated")
        self.assertContains(teacher_response, "Analyze metrics")

        self.client.force_login(self.admin)
        response = self.client.get(reverse("analytics:administrator"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Course usage")

        self.client.force_login(self.student)
        self.assertEqual(self.client.get(reverse("analytics:teacher")).status_code, 403)
        self.assertEqual(self.client.get(reverse("analytics:administrator")).status_code, 403)

    def test_teacher_can_trigger_ai_analyzer(self):
        self.client.force_login(self.teacher)

        response = self.client.post(reverse("analytics:teacher-analyze"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Analysis ready")
        self.assertContains(response, "Actionable insights")
        self.assertContains(response, "Suggested next steps")

    def test_student_cannot_trigger_teacher_ai_analyzer(self):
        self.client.force_login(self.student)

        response = self.client.post(reverse("analytics:teacher-analyze"))

        self.assertEqual(response.status_code, 403)

    def test_teacher_metrics_use_completion_and_time_events(self):
        LessonProgress.objects.create(
            enrollment=self.enrollment,
            lesson_version=self.lesson,
            status=LessonProgress.Status.COMPLETED,
        )
        CourseCompletion.objects.create(enrollment=self.enrollment, confirmed_by=self.teacher)
        self.client.force_login(self.student)
        self.client.post(
            reverse("analytics:lesson-time", args=[self.lesson.id]),
            {"duration_seconds": "180"},
        )

        metrics = teacher_course_metrics(self.course)

        self.assertEqual(metrics["completion_rate"], 100.0)
        self.assertEqual(metrics["lesson_metrics"][0]["minutes"], 3.0)
        self.assertEqual(metrics["lesson_metrics"][0]["dropoff_rate"], 0.0)

    def test_teacher_analytics_uses_a_fixed_number_of_bulk_queries(self):
        Course.objects.create(
            organization=self.organization,
            created_by=self.teacher,
            title="Second analytics course",
            slug="second-analytics-course",
        )

        with CaptureQueriesContext(connection) as queries:
            metrics = teacher_analytics(self.teacher)

        self.assertEqual(len(metrics), 2)
        self.assertLessEqual(len(queries), 7)
