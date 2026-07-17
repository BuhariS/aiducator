from django.test import TestCase, override_settings
from django.utils import timezone
from django.urls import reverse

from accounts.models import User
from ai_engine.models import AIJob
from courses.models import Course, CourseVersion, LessonVersion, Module
from enrollments.models import Enrollment
from organizations.models import Membership, Organization

from .models import Attempt, GradeDecision, Question, ReviewQueueItem, RubricVersion


@override_settings(CELERY_TASK_ALWAYS_EAGER=True, AI_LLM_PROVIDER="fake")
class AttemptFlowTests(TestCase):
    def setUp(self):
        self.student = User.objects.create_user(email="student@example.com", password="StrongPass123!")
        self.teacher = User.objects.create_user(email="teacher@example.com", password="StrongPass123!")
        organization = Organization.objects.create(name="Pilot School", slug="pilot-school")
        course = Course.objects.create(
            organization=organization,
            created_by=self.teacher,
            title="Python Fundamentals",
            slug="python-fundamentals",
            status=Course.Status.PUBLISHED,
        )
        Membership.objects.create(organization=organization, user=self.teacher, role=Membership.Role.TEACHER)
        Membership.objects.create(organization=organization, user=self.student, role=Membership.Role.STUDENT)
        version = CourseVersion.objects.create(course=course, version_number=1, status=CourseVersion.Status.DRAFT)
        module = Module.objects.create(course_version=version, title="Variables", position=1)
        lesson = LessonVersion.objects.create(module=module, title="Values", content="Learn values.", position=1)
        self.question = Question.objects.create(lesson_version=lesson, question_type=Question.QuestionType.EXPLANATION, prompt="Explain a variable.")
        RubricVersion.objects.create(
            question=self.question,
            criteria=[{"criterion": "Explains storage of a value", "weight": 100}],
            approved_by=self.teacher,
        )
        version.status = CourseVersion.Status.PUBLISHED
        version.approved_by = self.teacher
        version.approved_at = timezone.now()
        version.save(update_fields=["status", "approved_by", "approved_at"])
        self.enrollment = Enrollment.objects.create(course=course, course_version=version, student=self.student)

    def test_submission_creates_attempt_and_ai_job(self):
        self.client.force_login(self.student)
        with self.captureOnCommitCallbacks(execute=True):
            response = self.client.post(
                reverse("assessments:submit", kwargs={"question_id": self.question.id}),
                {"answer_text": "A variable stores a value in a program."},
            )
        attempt = Attempt.objects.get()
        self.assertRedirects(response, reverse("assessments:attempt-status", kwargs={"attempt_id": attempt.id}))
        self.assertEqual(AIJob.objects.filter(entity_id=attempt.id).count(), 1)
        self.assertEqual(attempt.status, Attempt.Status.AWAITING_REVIEW)
        self.assertEqual(ReviewQueueItem.objects.filter(attempt=attempt, status=ReviewQueueItem.Status.OPEN).count(), 1)

    def test_teacher_can_confirm_ai_grade(self):
        self.client.force_login(self.student)
        with self.captureOnCommitCallbacks(execute=True):
            self.client.post(
                reverse("assessments:submit", kwargs={"question_id": self.question.id}),
                {"answer_text": "A variable stores a value and the answer explains the concept clearly."},
            )
        review = ReviewQueueItem.objects.get()
        self.client.force_login(self.teacher)
        response = self.client.post(
            reverse("assessments:review-detail", kwargs={"review_id": review.id}),
            {"final_score": 85, "reason": "Clear explanation."},
        )
        self.assertRedirects(response, reverse("assessments:review-queue"))
        self.assertEqual(GradeDecision.objects.get(attempt=review.attempt).final_score, 85)
        self.assertEqual(review.__class__.objects.get(id=review.id).status, ReviewQueueItem.Status.RESOLVED)
        self.assertEqual(self.enrollment.lesson_progress.get().status, "completed")

    def test_fourth_attempt_is_rejected(self):
        Attempt.objects.bulk_create(
            [
                Attempt(enrollment=self.enrollment, question=self.question, attempt_number=number, answer_text="Existing answer")
                for number in (1, 2, 3)
            ]
        )
        self.client.force_login(self.student)
        response = self.client.post(
            reverse("assessments:submit", kwargs={"question_id": self.question.id}),
            {"answer_text": "A new answer that should not be accepted."},
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(Attempt.objects.count(), 3)
