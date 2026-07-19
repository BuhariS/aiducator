from types import SimpleNamespace
from unittest.mock import patch

from django.core.exceptions import PermissionDenied
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from accounts.models import User
from ai_engine.models import AIJob
from ai_engine.providers.base import ProviderGrade
from ai_engine.schemas import GradingResult
from courses.models import Course, CourseVersion, LessonVersion, Module
from enrollments.models import Enrollment
from organizations.models import Membership, Organization

from .models import (
    AccommodationRequest,
    Appeal,
    Attempt,
    GradeDecision,
    GradeEvent,
    ManualReview,
    Question,
    ReviewQueueItem,
    RubricVersion,
)
from .sandbox import execute_python_in_isolated_sandbox
from .views import finalize_review


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
        next_module = Module.objects.create(course_version=version, title="Control flow", position=2)
        self.next_lesson = LessonVersion.objects.create(
            module=next_module,
            title="Conditions",
            content="Learn conditions.",
            position=1,
        )
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
        self.assertEqual(len(attempt.submission.content_hash), 64)
        self.assertTrue(GradeEvent.objects.filter(attempt=attempt, event_type=GradeEvent.EventType.SUBMITTED).exists())
        self.assertTrue(ManualReview.objects.filter(attempt=attempt, status=ManualReview.Status.OPEN).exists())

    def test_student_sees_tentative_ai_grade_with_moderation_notice(self):
        self.client.force_login(self.student)
        with self.captureOnCommitCallbacks(execute=True):
            self.client.post(
                reverse("assessments:submit", kwargs={"question_id": self.question.id}),
                {"answer_text": "A variable stores a value and gives it a reusable name."},
            )

        attempt = Attempt.objects.get()
        response = self.client.get(reverse("assessments:attempt-status", kwargs={"attempt_id": attempt.id}))

        self.assertContains(response, "Your tentative AI grade is ready.")
        self.assertContains(response, "Tentative AI grade")
        self.assertContains(response, f"{attempt.ai_grade.suggested_score}%")
        self.assertContains(response, "Subject to teacher moderation")
        self.assertContains(response, "not your final result")

    def test_attempt_status_next_button_opens_the_next_module(self):
        self.client.force_login(self.student)
        with self.captureOnCommitCallbacks(execute=True):
            self.client.post(
                reverse("assessments:submit", kwargs={"question_id": self.question.id}),
                {"answer_text": "A variable stores a value and gives it a reusable name."},
            )

        attempt = Attempt.objects.get()
        response = self.client.get(reverse("assessments:attempt-status", kwargs={"attempt_id": attempt.id}))

        self.assertContains(response, "Next module")
        self.assertContains(
            response,
            f'href="{reverse("courses:learn-lesson", kwargs={"slug": self.enrollment.course.slug, "lesson_id": self.next_lesson.id})}"',
        )

    def test_course_map_marks_a_module_when_its_assessment_has_an_ai_grade(self):
        self.client.force_login(self.student)
        with self.captureOnCommitCallbacks(execute=True):
            self.client.post(
                reverse("assessments:submit", kwargs={"question_id": self.question.id}),
                {"answer_text": "A variable stores a value and gives it a reusable name."},
            )

        response = self.client.get(
            reverse(
                "courses:learn-lesson",
                kwargs={"slug": self.enrollment.course.slug, "lesson_id": self.question.lesson_version_id},
            )
        )

        self.assertContains(response, 'aria-label="Module complete"')

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

    def test_high_confidence_objective_result_is_auto_confirmed(self):
        Question.objects.filter(pk=self.question.pk).update(is_objective=True)
        provider_grade = ProviderGrade(
            result=GradingResult(
                score=90,
                confidence=0.99,
                strengths=["Accurate"],
                errors=[],
                feedback="Correct.",
                recommended_action="advance",
                requires_review=False,
            ),
            provider="test",
            model="test-model",
        )
        self.client.force_login(self.student)
        with patch("ai_engine.tasks.get_grading_provider") as get_provider:
            get_provider.return_value.grade.return_value = provider_grade
            with self.captureOnCommitCallbacks(execute=True):
                self.client.post(
                    reverse("assessments:submit", kwargs={"question_id": self.question.id}),
                    {"answer_text": "A variable stores a value for later use."},
                )
        attempt = Attempt.objects.get()
        self.assertEqual(attempt.status, Attempt.Status.GRADED)
        self.assertEqual(attempt.grade_decision.final_score, 90)
        self.assertFalse(ReviewQueueItem.objects.filter(attempt=attempt).exists())
        self.assertTrue(GradeEvent.objects.filter(attempt=attempt, event_type=GradeEvent.EventType.AUTO_CONFIRMED).exists())

    def test_student_can_appeal_and_approved_appeal_reopens_review(self):
        self.client.force_login(self.student)
        with self.captureOnCommitCallbacks(execute=True):
            self.client.post(
                reverse("assessments:submit", kwargs={"question_id": self.question.id}),
                {"answer_text": "A variable stores a value and can be reused in a program."},
            )
        review = ReviewQueueItem.objects.get()
        self.client.force_login(self.teacher)
        self.client.post(
            reverse("assessments:review-detail", kwargs={"review_id": review.id}),
            {"final_score": 75, "reason": "Reviewed against the rubric."},
        )
        attempt = review.attempt
        self.client.force_login(self.student)
        response = self.client.post(
            reverse("assessments:submit-appeal", kwargs={"attempt_id": attempt.id}),
            {"reason": "The rubric evidence in my answer was not considered."},
        )
        self.assertRedirects(response, reverse("assessments:attempt-status", kwargs={"attempt_id": attempt.id}))
        appeal = Appeal.objects.get(attempt=attempt)
        self.client.force_login(self.teacher)
        response = self.client.post(
            reverse("assessments:decide-appeal", kwargs={"appeal_id": appeal.id}),
            {"decision": Appeal.Status.APPROVED, "decision_note": "Reopen for a second review."},
        )
        self.assertRedirects(response, reverse("assessments:appeal-queue"))
        self.assertEqual(Appeal.objects.get(pk=appeal.pk).status, Appeal.Status.APPROVED)
        self.assertEqual(ManualReview.objects.get(attempt=attempt).status, ManualReview.Status.OPEN)

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

    def test_student_can_request_and_teacher_can_approve_copy_paste_support(self):
        self.client.force_login(self.student)
        response = self.client.post(
            reverse("assessments:request-accommodation"),
            {
                "course": self.enrollment.course_id,
                "accommodation_type": AccommodationRequest.AccommodationType.COPY_PASTE,
                "details": "I need assistive input support for controlled assessments.",
            },
        )
        self.assertRedirects(response, reverse("assessments:accommodation-requested"))
        request = AccommodationRequest.objects.get()
        self.client.force_login(self.teacher)
        response = self.client.post(
            reverse("assessments:decide-accommodation", kwargs={"request_id": request.id}),
            {"decision": AccommodationRequest.Status.APPROVED},
        )
        self.assertRedirects(response, reverse("assessments:accommodation-queue"))
        self.client.force_login(self.student)
        response = self.client.get(reverse("assessments:submit", kwargs={"question_id": self.question.id}))
        self.assertContains(response, "approved accessibility accommodation is active")
        self.assertNotContains(response, 'data-protected-input="true"')

    def test_review_service_rejects_teacher_from_another_organization(self):
        outsider = User.objects.create_user(email="outsider@example.com", password="StrongPass123!")
        review = ReviewQueueItem.objects.create(
            attempt=Attempt.objects.create(
                enrollment=self.enrollment,
                question=self.question,
                attempt_number=1,
                answer_text="An answer.",
            ),
            reason="Manual review",
        )
        with self.assertRaises(PermissionDenied):
            finalize_review(review, outsider, 70)


class SandboxSecurityTests(TestCase):
    @patch("assessments.sandbox.shutil.which", return_value="/usr/bin/docker")
    @patch("assessments.sandbox.subprocess.run")
    def test_sandbox_applies_resource_and_network_restrictions(self, run, which):
        run.side_effect = [
            SimpleNamespace(returncode=0),
            SimpleNamespace(returncode=0, stdout="", stderr=""),
        ]

        result = execute_python_in_isolated_sandbox("print(2 + 2)")

        self.assertEqual(result["status"], "succeeded")
        command = run.call_args_list[1].args[0]
        self.assertIn("--network=none", command)
        self.assertIn("--read-only", command)
        self.assertIn("--cap-drop=ALL", command)
        self.assertIn("--user=65532:65532", command)
        self.assertIn("--pids-limit=32", command)
        self.assertIn("--ulimit=cpu=2:2", command)
        self.assertIn("-I", command)
        self.assertIn("-B", command)
