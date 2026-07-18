from django.core.exceptions import PermissionDenied
from django.test import TestCase

from accounts.models import User
from courses.models import Course, CourseVersion, LessonVersion, Module
from enrollments.models import Enrollment, LessonProgress
from organizations.models import Membership, Organization

from .models import BadgeAward, PraiseNotification, StreakEvent, XPEvent
from .services import correct_xp, record_learning_reward


class GamificationServiceTests(TestCase):
    def setUp(self):
        self.teacher = User.objects.create_user(email="teacher@example.com", password="StrongPass123!")
        self.student = User.objects.create_user(email="student@example.com", password="StrongPass123!")
        organization = Organization.objects.create(name="Gamification School", slug="gamification-school")
        Membership.objects.create(organization=organization, user=self.teacher, role=Membership.Role.TEACHER)
        Membership.objects.create(organization=organization, user=self.student, role=Membership.Role.STUDENT)
        course = Course.objects.create(
            organization=organization,
            created_by=self.teacher,
            title="Python Practice",
            slug="python-practice",
            status=Course.Status.DRAFT,
        )
        version = CourseVersion.objects.create(course=course, version_number=1, status=CourseVersion.Status.DRAFT)
        module = Module.objects.create(course_version=version, title="Basics", position=1)
        lesson = LessonVersion.objects.create(
            module=module,
            title="Variables",
            content="A variable gives a name to a value.",
            objectives=["Explain variables"],
            position=1,
            status=LessonVersion.Status.DRAFT,
        )
        self.enrollment = Enrollment.objects.create(course=course, course_version=version, student=self.student)
        self.progress = LessonProgress.objects.create(enrollment=self.enrollment, lesson_version=lesson)

    def test_learning_reward_is_idempotent_and_explained(self):
        first = record_learning_reward(
            enrollment=self.enrollment,
            event_type="lesson_completed",
            source=self.progress,
            points=5,
            reason="Completed lesson content",
            praise="Well done.",
            badge_key="first_lesson",
        )
        second = record_learning_reward(
            enrollment=self.enrollment,
            event_type="lesson_completed",
            source=self.progress,
            points=5,
            reason="Completed lesson content",
            praise="Well done.",
            badge_key="first_lesson",
        )

        self.assertEqual(first["xp"].id, second["xp"].id)
        self.assertEqual(XPEvent.objects.count(), 1)
        self.assertEqual(XPEvent.objects.get().reason, "Completed lesson content")
        self.assertEqual(StreakEvent.objects.count(), 1)
        self.assertEqual(PraiseNotification.objects.count(), 1)
        self.assertEqual(BadgeAward.objects.count(), 1)

    def test_xp_correction_requires_teacher_and_records_reason(self):
        event = record_learning_reward(
            enrollment=self.enrollment,
            event_type="lesson_completed",
            source=self.progress,
            points=5,
            reason="Completed lesson content",
            praise="Well done.",
        )["xp"]

        with self.assertRaises(PermissionDenied):
            correct_xp(event, points=-5, reason="Duplicate award", actor=self.student)

        correction = correct_xp(event, points=-5, reason="Duplicate award", actor=self.teacher)
        self.assertEqual(correction.correction_for_id, event.id)
        self.assertEqual(correction.points, -5)
        self.assertEqual(correction.reason, "Duplicate award")
