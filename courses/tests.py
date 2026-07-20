from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse

from accounts.models import User
from ai_engine.models import AIJob, CourseGenerationRequest
from analytics.models import AuditEvent
from assessments.models import Attempt, GradeDecision, Question, RubricVersion
from enrollments.models import CourseCompletion, Enrollment
from organizations.models import Membership, Organization

from .models import Course, CourseVersion, FinalProject, LessonArtifact, LessonVersion, Module


class CourseFlowTests(TestCase):
    def setUp(self):
        self.student = User.objects.create_user(email="student@example.com", password="StrongPass123!")
        self.organization = Organization.objects.create(name="Aiducator Pilot", slug="aiducator-pilot")
        Membership.objects.create(organization=self.organization, user=self.student, role=Membership.Role.STUDENT)
        self.course = Course.objects.create(
            organization=self.organization,
            created_by=self.student,
            title="Python Fundamentals",
            slug="python-fundamentals",
            description="A beginner course.",
            status=Course.Status.PUBLISHED,
        )
        CourseVersion.objects.create(course=self.course, version_number=1, status=CourseVersion.Status.PUBLISHED)

    def test_student_can_enroll_in_published_course(self):
        self.client.force_login(self.student)
        response = self.client.post(reverse("courses:enroll", kwargs={"slug": self.course.slug}))
        self.assertRedirects(response, reverse("courses:learn", kwargs={"slug": self.course.slug}))
        self.assertEqual(self.course.enrollments.count(), 1)

    def _completed_enrollment_with_average(self, score):
        version = CourseVersion.objects.create(course=self.course, version_number=2, status=CourseVersion.Status.DRAFT)
        module = Module.objects.create(course_version=version, title="Assessment", position=1)
        lesson = LessonVersion.objects.create(module=module, title="Final check", content="Show what you learned.", position=1)
        question = Question.objects.create(
            lesson_version=lesson,
            question_type=Question.QuestionType.EXPLANATION,
            prompt="Explain the main concept.",
        )
        version.status = CourseVersion.Status.PUBLISHED
        version.save(update_fields=["status"])
        enrollment = Enrollment.objects.create(course=self.course, course_version=version, student=self.student)
        attempt = Attempt.objects.create(
            enrollment=enrollment,
            question=question,
            attempt_number=1,
            answer_text="My completed answer.",
            status=Attempt.Status.GRADED,
        )
        GradeDecision.objects.create(
            attempt=attempt,
            final_score=score,
            status=GradeDecision.Status.CONFIRMED,
        )
        CourseCompletion.objects.create(enrollment=enrollment, confirmed_by=self.student)
        return enrollment

    def test_completed_course_card_shows_graduated_when_average_meets_pass_mark(self):
        self._completed_enrollment_with_average(self.course.passing_score)
        self.client.force_login(self.student)

        response = self.client.get(reverse("dashboard:student-dashboard"))

        self.assertContains(response, "Graduated")
        self.assertNotContains(response, "Unenroll")

    def test_completed_course_card_shows_retry_when_average_is_below_pass_mark(self):
        self._completed_enrollment_with_average(self.course.passing_score - 1)
        self.client.force_login(self.student)

        response = self.client.get(reverse("dashboard:student-dashboard"))

        self.assertContains(response, "Retry")
        self.assertNotContains(response, "Unenroll")

    def test_course_map_marks_submitted_assessment_complete_while_awaiting_review(self):
        version = CourseVersion.objects.create(course=self.course, version_number=2, status=CourseVersion.Status.DRAFT)
        module = Module.objects.create(course_version=version, title="Practice", position=1)
        lesson = LessonVersion.objects.create(
            module=module,
            title="Variable practice",
            content="Submit your explanation.",
            position=1,
            status=LessonVersion.Status.PUBLISHED,
        )
        question = Question.objects.create(
            lesson_version=lesson,
            question_type=Question.QuestionType.EXPLANATION,
            prompt="Explain how a variable stores a value.",
        )
        version.status = CourseVersion.Status.PUBLISHED
        version.save(update_fields=["status"])
        enrollment = Enrollment.objects.create(course=self.course, course_version=version, student=self.student)
        Attempt.objects.create(
            enrollment=enrollment,
            question=question,
            attempt_number=1,
            answer_text="A variable gives a value a name.",
            status=Attempt.Status.AWAITING_REVIEW,
        )
        self.client.force_login(self.student)

        response = self.client.get(
            reverse("courses:learn-lesson", kwargs={"slug": self.course.slug, "lesson_id": lesson.id})
        )

        self.assertContains(response, "Your answer is awaiting teacher review.")
        self.assertContains(response, '<span aria-label="Completed">✓</span>')

    def test_student_enrolls_in_latest_published_course_version(self):
        latest_version = CourseVersion.objects.create(
            course=self.course,
            version_number=2,
            status=CourseVersion.Status.PUBLISHED,
        )
        self.client.force_login(self.student)
        response = self.client.post(reverse("courses:enroll", kwargs={"slug": self.course.slug}))
        self.assertRedirects(response, reverse("courses:learn", kwargs={"slug": self.course.slug}))
        self.assertEqual(self.course.enrollments.get().course_version, latest_version)

    def test_student_can_unenroll_from_course(self):
        enrollment = Enrollment.objects.create(
            course=self.course,
            course_version=self.course.versions.get(),
            student=self.student,
        )
        self.client.force_login(self.student)
        dashboard_response = self.client.get(reverse("dashboard:student-dashboard"))
        self.assertContains(dashboard_response, "Unenroll")

        response = self.client.post(reverse("courses:unenroll", kwargs={"slug": self.course.slug}))

        self.assertRedirects(response, reverse("dashboard:student-dashboard"))
        enrollment.refresh_from_db()
        self.assertEqual(enrollment.status, Enrollment.Status.WITHDRAWN)
        dashboard_response = self.client.get(reverse("dashboard:student-dashboard"))
        self.assertNotContains(dashboard_response, self.course.title)

    def test_student_can_reenroll_after_unenrolling(self):
        Enrollment.objects.create(
            course=self.course,
            course_version=self.course.versions.get(),
            student=self.student,
            status=Enrollment.Status.WITHDRAWN,
        )
        self.client.force_login(self.student)

        response = self.client.post(reverse("courses:enroll", kwargs={"slug": self.course.slug}))

        self.assertRedirects(response, reverse("courses:learn", kwargs={"slug": self.course.slug}))
        self.assertEqual(self.course.enrollments.get().status, Enrollment.Status.ACTIVE)

    def test_next_button_opens_first_lesson_of_next_module(self):
        learning_version = CourseVersion.objects.create(
            course=self.course,
            version_number=2,
            status=CourseVersion.Status.DRAFT,
        )
        first_module = Module.objects.create(course_version=learning_version, title="Basics", position=1)
        first_lesson = LessonVersion.objects.create(
            module=first_module,
            title="Variables",
            objectives=["Use variables"],
            content="Variables store values.",
            position=1,
            status=LessonVersion.Status.PUBLISHED,
        )
        next_module = Module.objects.create(course_version=learning_version, title="Control flow", position=2)
        next_lesson = LessonVersion.objects.create(
            module=next_module,
            title="Conditions",
            objectives=["Use conditions"],
            content="Conditions choose paths.",
            position=1,
            status=LessonVersion.Status.PUBLISHED,
        )
        learning_version.status = CourseVersion.Status.PUBLISHED
        learning_version.save(update_fields=["status"])
        enrollment = Enrollment.objects.create(
            course=self.course,
            course_version=learning_version,
            student=self.student,
        )
        CourseCompletion.objects.create(enrollment=enrollment, confirmed_by=self.student)
        self.client.force_login(self.student)

        response = self.client.get(
            reverse("courses:learn-lesson", kwargs={"slug": self.course.slug, "lesson_id": first_lesson.id})
        )

        self.assertContains(response, "Learning objectives")
        self.assertContains(response, "Congratulations — you completed Python Fundamentals!")
        self.assertContains(response, ">Next<")
        self.assertContains(
            response,
            f'href="{reverse("courses:learn-lesson", kwargs={"slug": self.course.slug, "lesson_id": next_lesson.id})}"',
        )

    def test_lesson_markdown_and_youtube_video_are_rendered(self):
        version = CourseVersion.objects.create(course=self.course, version_number=2, status=CourseVersion.Status.DRAFT)
        module = Module.objects.create(course_version=version, title="Basics", position=1)
        lesson = LessonVersion.objects.create(
            module=module,
            title="Variables",
            objectives=["Use variables"],
            content="## A useful heading\n\nVariables store values.",
            position=1,
            status=LessonVersion.Status.PUBLISHED,
        )
        LessonArtifact.objects.create(
            lesson_version=lesson,
            artifact_type=LessonArtifact.ArtifactType.VIDEO,
            content="https://www.youtube.com/watch?v=rfscVS0vtbw",
            position=1,
        )
        version.status = CourseVersion.Status.PUBLISHED
        version.save(update_fields=["status"])
        Enrollment.objects.create(course=self.course, course_version=version, student=self.student)
        self.client.force_login(self.student)

        response = self.client.get(reverse("courses:learn-lesson", kwargs={"slug": self.course.slug, "lesson_id": lesson.id}))

        self.assertContains(response, "<h2>A useful heading</h2>", html=True)
        self.assertContains(response, "https://www.youtube-nocookie.com/embed/rfscVS0vtbw")

    @override_settings(CELERY_TASK_ALWAYS_EAGER=True, AI_LLM_PROVIDER="fake")
    def test_student_can_submit_final_project_and_receive_review_notification(self):
        version = CourseVersion.objects.create(course=self.course, version_number=2, status=CourseVersion.Status.DRAFT)
        module = Module.objects.create(course_version=version, title="Final module", position=1)
        lesson = LessonVersion.objects.create(
            module=module,
            title="Final lesson",
            objectives=["Finish the project"],
            content="Prepare your final project.",
            position=1,
            status=LessonVersion.Status.PUBLISHED,
        )
        project = FinalProject.objects.create(
            course_version=version,
            title="Build a calculator",
            brief="Build and explain a small calculator program for your class.",
            objectives=["Use Python"],
            requirements=["Write Python code"],
            deliverables=["A project link"],
            rubric=[{"criterion": "Uses the required concept", "weight": 100}],
        )
        version.status = CourseVersion.Status.PUBLISHED
        version.save(update_fields=["status"])
        enrollment = Enrollment.objects.create(course=self.course, course_version=version, student=self.student)
        self.client.force_login(self.student)

        response = self.client.get(reverse("courses:learn-lesson", kwargs={"slug": self.course.slug, "lesson_id": lesson.id}))
        self.assertContains(response, "Submit your project for AI review")
        self.assertContains(response, "Final project")
        self.assertContains(
            response,
            f'{reverse("courses:learn-lesson", kwargs={"slug": self.course.slug, "lesson_id": lesson.id})}#final-project',
        )
        with self.captureOnCommitCallbacks(execute=True):
            response = self.client.post(
                reverse("courses:submit-final-project", kwargs={"slug": self.course.slug}),
                {"answer_text": "https://example.com/my-calculator-project with a short explanation."},
            )

        self.assertRedirects(
            response,
            reverse("courses:learn-lesson", kwargs={"slug": self.course.slug, "lesson_id": lesson.id}),
        )
        submission = project.submissions.get(enrollment=enrollment)
        job = AIJob.objects.get(entity_id=submission.id)
        self.assertEqual(job.status, AIJob.Status.SUCCEEDED, job.error_message)
        self.assertEqual(submission.status, "reviewed")
        self.assertEqual(submission.suggested_score, 60)
        self.assertTrue(self.student.notifications.filter(notification_type="project_reviewed").exists())


class CourseAuthoringTests(TestCase):
    def setUp(self):
        self.teacher = User.objects.create_user(email="teacher@example.com", password="StrongPass123!")
        self.organization = Organization.objects.create(name="Authoring School", slug="authoring-school")
        Membership.objects.create(
            organization=self.organization,
            user=self.teacher,
            role=Membership.Role.TEACHER,
        )
        self.course = Course.objects.create(
            organization=self.organization,
            created_by=self.teacher,
            title="Draft Python Course",
            slug="draft-python-course",
            status=Course.Status.DRAFT,
        )
        self.client.force_login(self.teacher)

    def test_teacher_can_create_a_course_from_dashboard(self):
        response = self.client.post(
            reverse("teacher_courses:create"),
            {
                "title": "Python for Beginners",
                "description": "A practical first Python course.",
                "duration_weeks": 12,
                "passing_score": 70,
                "max_retries": 2,
            },
        )
        course = Course.objects.get(title="Python for Beginners")
        draft = CourseVersion.objects.get(course=course)
        self.assertEqual(course.created_by, self.teacher)
        self.assertEqual(course.organization, self.organization)
        self.assertEqual(draft.status, CourseVersion.Status.DRAFT)
        self.assertRedirects(
            response,
            reverse("teacher_courses:version-editor", kwargs={"slug": course.slug, "version_id": draft.id}),
        )

    def test_course_builder_shows_guided_steps(self):
        version = CourseVersion.objects.create(course=self.course, version_number=1, status=CourseVersion.Status.DRAFT)
        response = self.client.get(
            reverse("teacher_courses:version-editor", kwargs={"slug": self.course.slug, "version_id": version.id})
        )
        self.assertContains(response, "Course Builder")
        self.assertContains(response, "Course setup")
        self.assertContains(response, "Assessments and rubrics")
        self.assertContains(response, "Finish these items before publishing")

    def test_module_and_lesson_forms_continue_to_materials_review(self):
        version = CourseVersion.objects.create(course=self.course, version_number=1, status=CourseVersion.Status.DRAFT)
        response = self.client.post(
            reverse("teacher_courses:add-module", kwargs={"slug": self.course.slug, "version_id": version.id}),
            {"title": "Python basics", "position": 1, "next": "lesson"},
        )
        module = Module.objects.get(course_version=version)
        self.assertRedirects(
            response,
            reverse(
                "teacher_courses:create-lesson",
                kwargs={"slug": self.course.slug, "version_id": version.id, "module_id": module.id},
            ),
        )

        response = self.client.post(
            reverse(
                "teacher_courses:create-lesson",
                kwargs={"slug": self.course.slug, "version_id": version.id, "module_id": module.id},
            ),
            {
                "title": "Variables",
                "position": 1,
                "content": "A variable gives a name to a value in a Python program.",
            },
        )
        lesson = LessonVersion.objects.get(module=module)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(
            response.url,
            f"{reverse('teacher_courses:version-editor', kwargs={'slug': self.course.slug, 'version_id': version.id})}#lesson-{lesson.id}-materials",
        )

    def test_teacher_can_edit_module_and_continue_to_first_lesson(self):
        version = CourseVersion.objects.create(course=self.course, version_number=1, status=CourseVersion.Status.DRAFT)
        module = Module.objects.create(course_version=version, title="Original theme", position=1)
        lesson = LessonVersion.objects.create(module=module, title="First lesson", content="Draft.", position=1)

        response = self.client.get(
            reverse(
                "teacher_courses:edit-module",
                kwargs={"slug": self.course.slug, "version_id": version.id, "module_id": module.id},
            )
        )
        self.assertContains(response, "Edit module")

        response = self.client.post(
            reverse(
                "teacher_courses:edit-module",
                kwargs={"slug": self.course.slug, "version_id": version.id, "module_id": module.id},
            ),
            {"title": "Updated theme", "position": 1, "next": "lesson"},
        )
        self.assertRedirects(
            response,
            reverse(
                "teacher_courses:edit-lesson",
                kwargs={
                    "slug": self.course.slug,
                    "version_id": version.id,
                    "module_id": module.id,
                    "lesson_id": lesson.id,
                },
            ),
        )
        module.refresh_from_db()
        self.assertEqual(module.title, "Updated theme")

        response = self.client.get(
            reverse(
                "teacher_courses:edit-lesson",
                kwargs={
                    "slug": self.course.slug,
                    "version_id": version.id,
                    "module_id": module.id,
                    "lesson_id": lesson.id,
                },
            )
        )
        self.assertContains(response, "Save and review learning materials")
        self.assertNotContains(response, "Learning objectives")

    def test_module_editor_can_continue_to_the_next_module(self):
        version = CourseVersion.objects.create(course=self.course, version_number=1, status=CourseVersion.Status.DRAFT)
        first_module = Module.objects.create(course_version=version, title="First module", position=1)
        second_module = Module.objects.create(course_version=version, title="Second module", position=2)

        response = self.client.post(
            reverse(
                "teacher_courses:edit-module",
                kwargs={"slug": self.course.slug, "version_id": version.id, "module_id": first_module.id},
            ),
            {"title": "Updated first module", "position": 1, "next": "module"},
        )

        self.assertRedirects(
            response,
            reverse(
                "teacher_courses:edit-module",
                kwargs={"slug": self.course.slug, "version_id": version.id, "module_id": second_module.id},
            ),
        )

    def test_lesson_editor_can_continue_to_the_next_lesson(self):
        version = CourseVersion.objects.create(course=self.course, version_number=1, status=CourseVersion.Status.DRAFT)
        module = Module.objects.create(course_version=version, title="Foundations", position=1)
        first_lesson = LessonVersion.objects.create(module=module, title="First lesson", content="First draft.", position=1)
        second_lesson = LessonVersion.objects.create(module=module, title="Second lesson", content="Second draft.", position=2)

        response = self.client.post(
            reverse(
                "teacher_courses:edit-lesson",
                kwargs={
                    "slug": self.course.slug,
                    "version_id": version.id,
                    "module_id": module.id,
                    "lesson_id": first_lesson.id,
                },
            ),
            {"title": "First lesson", "position": 1, "content": "Updated first lesson.", "next": "lesson"},
        )

        self.assertRedirects(
            response,
            reverse(
                "teacher_courses:edit-lesson",
                kwargs={
                    "slug": self.course.slug,
                    "version_id": version.id,
                    "module_id": module.id,
                    "lesson_id": second_lesson.id,
                },
            ),
        )

    def test_editor_links_to_module_editing_and_orders_materials_before_assessments(self):
        version = CourseVersion.objects.create(course=self.course, version_number=1, status=CourseVersion.Status.DRAFT)
        module = Module.objects.create(course_version=version, title="Foundations", position=1)
        lesson = LessonVersion.objects.create(
            module=module,
            title="Variables",
            objectives=["Explain how variables hold values", "Name variables clearly"],
            content="## Lesson content\n\nUse a meaningful name for each value.",
            position=1,
        )
        LessonArtifact.objects.create(lesson_version=lesson, artifact_type="text", content="M" * 500)
        Question.objects.create(lesson_version=lesson, question_type="scenario", prompt="Q" * 500)
        FinalProject.objects.create(
            course_version=version,
            title="Build a variable tracker",
            brief="Create a small practical tracker using named variables.",
        )

        response = self.client.get(
            reverse("teacher_courses:version-editor", kwargs={"slug": self.course.slug, "version_id": version.id})
        )

        self.assertContains(
            response,
            reverse(
                "teacher_courses:edit-module",
                kwargs={"slug": self.course.slug, "version_id": version.id, "module_id": module.id},
            ),
        )
        self.assertContains(response, "Continue to assessments and rubrics")
        self.assertContains(response, "M" * 500)
        self.assertContains(response, "Q" * 500)
        self.assertContains(response, "Learning objectives")
        self.assertContains(response, "Explain how variables hold values")
        self.assertContains(response, "<h2>Lesson content</h2>", html=True)
        page = response.content.decode()
        self.assertLess(page.index(f'id="lesson-{lesson.id}-assessments"'), page.index('id="final-project"'))
        self.assertLess(page.index('id="final-project"'), page.index('id="publish"'))

    def test_teacher_can_edit_course_setup_before_publishing(self):
        response = self.client.post(
            reverse("teacher_courses:settings", kwargs={"slug": self.course.slug}),
            {
                "title": "Updated Python Course",
                "description": "Updated course description for Nigerian learners.",
                "duration_weeks": 12,
                "passing_score": 70,
                "max_retries": 2,
            },
        )
        self.assertRedirects(response, reverse("teacher_courses:studio", kwargs={"slug": "updated-python-course"}))
        self.course.refresh_from_db()
        self.assertEqual(self.course.title, "Updated Python Course")

    def test_student_cannot_create_a_course(self):
        student = User.objects.create_user(email="student-authoring@example.com", password="StrongPass123!")
        Membership.objects.create(
            organization=self.organization,
            user=student,
            role=Membership.Role.STUDENT,
        )
        self.client.force_login(student)
        response = self.client.get(reverse("teacher_courses:create"))
        self.assertEqual(response.status_code, 403)

    def test_course_creator_can_delete_draft_course(self):
        response = self.client.post(reverse("teacher_courses:delete", kwargs={"slug": self.course.slug}))
        self.assertRedirects(response, reverse("dashboard:teacher-dashboard"))
        self.assertFalse(Course.objects.filter(id=self.course.id).exists())

    def test_another_teacher_cannot_delete_course(self):
        other_teacher = User.objects.create_user(email="other-teacher@example.com", password="StrongPass123!")
        Membership.objects.create(
            organization=self.organization,
            user=other_teacher,
            role=Membership.Role.TEACHER,
        )
        self.client.force_login(other_teacher)
        response = self.client.post(reverse("teacher_courses:delete", kwargs={"slug": self.course.slug}))
        self.assertEqual(response.status_code, 403)
        self.assertTrue(Course.objects.filter(id=self.course.id).exists())

    def test_published_course_cannot_be_deleted(self):
        self.course.status = Course.Status.PUBLISHED
        self.course.save(update_fields=["status"])
        response = self.client.post(reverse("teacher_courses:delete", kwargs={"slug": self.course.slug}))
        self.assertRedirects(response, reverse("teacher_courses:studio", kwargs={"slug": self.course.slug}))
        self.assertTrue(Course.objects.filter(id=self.course.id).exists())

    def test_enrolled_draft_course_cannot_be_deleted(self):
        version = CourseVersion.objects.create(course=self.course, version_number=1, status=CourseVersion.Status.DRAFT)
        student = User.objects.create_user(email="enrolled-student@example.com", password="StrongPass123!")
        Enrollment.objects.create(course=self.course, course_version=version, student=student)
        response = self.client.post(reverse("teacher_courses:delete", kwargs={"slug": self.course.slug}))
        self.assertRedirects(response, reverse("teacher_courses:studio", kwargs={"slug": self.course.slug}))
        self.assertTrue(Course.objects.filter(id=self.course.id).exists())

    def test_teacher_can_build_and_publish_course_version(self):
        response = self.client.post(reverse("teacher_courses:create-version", kwargs={"slug": self.course.slug}))
        version = CourseVersion.objects.get(course=self.course)
        self.assertRedirects(
            response,
            reverse("teacher_courses:version-editor", kwargs={"slug": self.course.slug, "version_id": version.id}),
        )

        response = self.client.post(
            reverse("teacher_courses:add-module", kwargs={"slug": self.course.slug, "version_id": version.id}),
            {"title": "Variables", "position": 1},
        )
        module = Module.objects.get(course_version=version)
        self.assertRedirects(
            response,
            reverse("teacher_courses:version-editor", kwargs={"slug": self.course.slug, "version_id": version.id}),
        )

        self.client.post(
            reverse(
                "teacher_courses:create-lesson",
                kwargs={"slug": self.course.slug, "version_id": version.id, "module_id": module.id},
            ),
            {
                "title": "Variable foundations",
                "position": 1,
                "objectives_text": "Explain variables\nUse variables in Python",
                "content": "A variable gives a name to a value.",
            },
        )
        lesson = LessonVersion.objects.get(module=module)
        self.client.post(
            reverse(
                "teacher_courses:create-question",
                kwargs={"slug": self.course.slug, "version_id": version.id, "lesson_id": lesson.id},
            ),
            {
                "question_type": "explanation",
                "prompt": "Explain what a variable is.",
                "max_score": 100,
                "position": 1,
                "is_active": "on",
                "criteria_text": "Uses accurate terminology\nGives a relevant example",
                "total_score": 100,
            },
        )
        response = self.client.post(
            reverse("teacher_courses:publish-version", kwargs={"slug": self.course.slug, "version_id": version.id})
        )
        version.refresh_from_db()
        self.assertRedirects(response, reverse("teacher_courses:studio", kwargs={"slug": self.course.slug}))
        self.assertEqual(version.status, CourseVersion.Status.PUBLISHED)
        self.assertEqual(self.course.__class__.objects.get(id=self.course.id).status, Course.Status.PUBLISHED)
        self.assertEqual(lesson.__class__.objects.get(id=lesson.id).status, LessonVersion.Status.PUBLISHED)

    def test_published_version_rejects_content_edits(self):
        version = CourseVersion.objects.create(
            course=self.course,
            version_number=1,
            status=CourseVersion.Status.DRAFT,
        )
        module = Module.objects.create(course_version=version, title="Variables", position=1)
        version.status = CourseVersion.Status.PUBLISHED
        version.save(update_fields=["status"])
        module.title = "Changed after publish"
        with self.assertRaises(ValidationError):
            module.save()

    def test_teacher_can_add_material_and_preview_student_experience(self):
        version = CourseVersion.objects.create(course=self.course, version_number=1, status=CourseVersion.Status.DRAFT)
        module = Module.objects.create(course_version=version, title="Getting started", position=1)
        lesson = LessonVersion.objects.create(
            module=module,
            title="Welcome",
            objectives=["Navigate the course"],
            content="Welcome to the course.",
            position=1,
        )
        response = self.client.post(
            reverse(
                "teacher_courses:create-artifact",
                kwargs={"slug": self.course.slug, "version_id": version.id, "lesson_id": lesson.id},
            ),
            {
                "artifact_type": "image",
                "content": "",
                "position": 0,
                "is_active": "on",
                "asset": SimpleUploadedFile("welcome.png", b"fake-image", content_type="image/png"),
            },
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(
            response.url,
            f"{reverse('teacher_courses:version-editor', kwargs={'slug': self.course.slug, 'version_id': version.id})}#lesson-{lesson.id}-materials",
        )
        self.assertTrue(LessonArtifact.objects.filter(lesson_version=lesson, artifact_type="image").exists())
        response = self.client.get(
            reverse("teacher_courses:preview-version", kwargs={"slug": self.course.slug, "version_id": version.id})
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Welcome")

    def test_teacher_can_remove_draft_material_and_assessment(self):
        version = CourseVersion.objects.create(course=self.course, version_number=1, status=CourseVersion.Status.DRAFT)
        module = Module.objects.create(course_version=version, title="Getting started", position=1)
        lesson = LessonVersion.objects.create(module=module, title="Welcome", content="Welcome.", position=1)
        artifact = LessonArtifact.objects.create(
            lesson_version=lesson,
            artifact_type=LessonArtifact.ArtifactType.TEXT,
            content="Read this first.",
        )
        question = Question.objects.create(
            lesson_version=lesson,
            question_type=Question.QuestionType.EXPLANATION,
            prompt="Explain the welcome lesson.",
        )
        rubric = RubricVersion.objects.create(
            question=question,
            version_number=1,
            criteria=[{"criterion": "Uses a clear explanation.", "weight": 100}],
        )

        editor_response = self.client.get(
            reverse("teacher_courses:version-editor", kwargs={"slug": self.course.slug, "version_id": version.id})
        )
        self.assertContains(
            editor_response,
            reverse(
                "teacher_courses:edit-artifact",
                kwargs={
                    "slug": self.course.slug,
                    "version_id": version.id,
                    "lesson_id": lesson.id,
                    "artifact_id": artifact.id,
                },
            ),
        )
        self.assertContains(
            editor_response,
            reverse(
                "teacher_courses:delete-artifact",
                kwargs={
                    "slug": self.course.slug,
                    "version_id": version.id,
                    "lesson_id": lesson.id,
                    "artifact_id": artifact.id,
                },
            ),
        )
        self.assertContains(
            editor_response,
            reverse(
                "teacher_courses:edit-question",
                kwargs={
                    "slug": self.course.slug,
                    "version_id": version.id,
                    "lesson_id": lesson.id,
                    "question_id": question.id,
                },
            ),
        )
        self.assertContains(
            editor_response,
            reverse(
                "teacher_courses:delete-question",
                kwargs={
                    "slug": self.course.slug,
                    "version_id": version.id,
                    "lesson_id": lesson.id,
                    "question_id": question.id,
                },
            ),
        )
        self.assertNotContains(editor_response, "Rubric ready")
        self.assertContains(
            editor_response,
            reverse(
                "teacher_courses:delete-artifacts",
                kwargs={"slug": self.course.slug, "version_id": version.id, "lesson_id": lesson.id},
            ),
        )
        self.assertContains(
            editor_response,
            reverse(
                "teacher_courses:delete-questions",
                kwargs={"slug": self.course.slug, "version_id": version.id, "lesson_id": lesson.id},
            ),
        )

        response = self.client.post(
            reverse(
                "teacher_courses:delete-artifact",
                kwargs={
                    "slug": self.course.slug,
                    "version_id": version.id,
                    "lesson_id": lesson.id,
                    "artifact_id": artifact.id,
                },
            )
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(
            response.url,
            f'{reverse("teacher_courses:version-editor", kwargs={"slug": self.course.slug, "version_id": version.id})}#lesson-{lesson.id}-materials',
        )
        self.assertFalse(LessonArtifact.objects.filter(id=artifact.id).exists())

        response = self.client.post(
            reverse(
                "teacher_courses:delete-question",
                kwargs={
                    "slug": self.course.slug,
                    "version_id": version.id,
                    "lesson_id": lesson.id,
                    "question_id": question.id,
                },
            )
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(
            response.url,
            f'{reverse("teacher_courses:version-editor", kwargs={"slug": self.course.slug, "version_id": version.id})}#lesson-{lesson.id}-assessments',
        )
        self.assertFalse(Question.objects.filter(id=question.id).exists())
        self.assertFalse(RubricVersion.objects.filter(id=rubric.id).exists())

    def test_teacher_can_remove_draft_modules_and_lessons(self):
        version = CourseVersion.objects.create(course=self.course, version_number=1, status=CourseVersion.Status.DRAFT)
        first_module = Module.objects.create(course_version=version, title="Remove me", position=1)
        LessonVersion.objects.create(module=first_module, title="Removed with module", content="Draft.", position=1)
        remaining_module = Module.objects.create(course_version=version, title="Keep me", position=2)
        lesson_to_remove = LessonVersion.objects.create(
            module=remaining_module,
            title="Remove this lesson",
            content="Draft.",
            position=1,
        )
        remaining_lesson = LessonVersion.objects.create(
            module=remaining_module,
            title="Keep this lesson",
            content="Draft.",
            position=2,
        )

        editor_response = self.client.get(
            reverse("teacher_courses:version-editor", kwargs={"slug": self.course.slug, "version_id": version.id})
        )
        self.assertContains(
            editor_response,
            reverse(
                "teacher_courses:delete-module",
                kwargs={"slug": self.course.slug, "version_id": version.id, "module_id": first_module.id},
            ),
        )
        self.assertContains(
            editor_response,
            reverse(
                "teacher_courses:delete-lesson",
                kwargs={
                    "slug": self.course.slug,
                    "version_id": version.id,
                    "module_id": remaining_module.id,
                    "lesson_id": lesson_to_remove.id,
                },
            ),
        )

        response = self.client.post(
            reverse(
                "teacher_courses:delete-module",
                kwargs={"slug": self.course.slug, "version_id": version.id, "module_id": first_module.id},
            )
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(
            response.url,
            f'{reverse("teacher_courses:version-editor", kwargs={"slug": self.course.slug, "version_id": version.id})}#lessons',
        )
        self.assertFalse(Module.objects.filter(id=first_module.id).exists())
        remaining_module.refresh_from_db()
        self.assertEqual(remaining_module.position, 1)

        response = self.client.post(
            reverse(
                "teacher_courses:delete-lesson",
                kwargs={
                    "slug": self.course.slug,
                    "version_id": version.id,
                    "module_id": remaining_module.id,
                    "lesson_id": lesson_to_remove.id,
                },
            )
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(
            response.url,
            f'{reverse("teacher_courses:version-editor", kwargs={"slug": self.course.slug, "version_id": version.id})}#module-{remaining_module.id}',
        )
        self.assertFalse(LessonVersion.objects.filter(id=lesson_to_remove.id).exists())
        remaining_lesson.refresh_from_db()
        self.assertEqual(remaining_lesson.position, 1)

    def test_teacher_can_remove_multiple_draft_materials_and_assessments(self):
        version = CourseVersion.objects.create(course=self.course, version_number=1, status=CourseVersion.Status.DRAFT)
        module = Module.objects.create(course_version=version, title="Getting started", position=1)
        lesson = LessonVersion.objects.create(module=module, title="Welcome", content="Welcome.", position=1)
        first_artifact = LessonArtifact.objects.create(
            lesson_version=lesson,
            artifact_type=LessonArtifact.ArtifactType.TEXT,
            content="Read this first.",
        )
        second_artifact = LessonArtifact.objects.create(
            lesson_version=lesson,
            artifact_type=LessonArtifact.ArtifactType.CODE,
            content="print('Hello')",
        )
        first_question = Question.objects.create(
            lesson_version=lesson,
            question_type=Question.QuestionType.EXPLANATION,
            prompt="Explain the lesson.",
        )
        second_question = Question.objects.create(
            lesson_version=lesson,
            question_type=Question.QuestionType.REFLECTION,
            prompt="Reflect on the lesson.",
        )
        first_rubric = RubricVersion.objects.create(
            question=first_question,
            version_number=1,
            criteria=[{"criterion": "Explains the topic.", "weight": 100}],
        )
        second_rubric = RubricVersion.objects.create(
            question=second_question,
            version_number=1,
            criteria=[{"criterion": "Reflects on learning.", "weight": 100}],
        )

        editor_response = self.client.get(
            reverse("teacher_courses:version-editor", kwargs={"slug": self.course.slug, "version_id": version.id})
        )
        self.assertLess(
            editor_response.content.find(f'id="lesson-{lesson.id}-materials"'.encode()),
            editor_response.content.find(f'id="lesson-{lesson.id}-assessments"'.encode()),
        )
        self.assertContains(editor_response, 'name="artifact_ids"', count=2)
        self.assertContains(editor_response, 'name="question_ids"', count=2)

        response = self.client.post(
            reverse(
                "teacher_courses:delete-artifacts",
                kwargs={"slug": self.course.slug, "version_id": version.id, "lesson_id": lesson.id},
            ),
            {"artifact_ids": [str(first_artifact.id), str(second_artifact.id)]},
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(
            response.url,
            f'{reverse("teacher_courses:version-editor", kwargs={"slug": self.course.slug, "version_id": version.id})}#lesson-{lesson.id}-materials',
        )
        self.assertFalse(LessonArtifact.objects.filter(id__in=[first_artifact.id, second_artifact.id]).exists())

        response = self.client.post(
            reverse(
                "teacher_courses:delete-questions",
                kwargs={"slug": self.course.slug, "version_id": version.id, "lesson_id": lesson.id},
            ),
            {"question_ids": [str(first_question.id), str(second_question.id)]},
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(
            response.url,
            f'{reverse("teacher_courses:version-editor", kwargs={"slug": self.course.slug, "version_id": version.id})}#lesson-{lesson.id}-assessments',
        )
        self.assertFalse(Question.objects.filter(id__in=[first_question.id, second_question.id]).exists())
        self.assertFalse(RubricVersion.objects.filter(id__in=[first_rubric.id, second_rubric.id]).exists())


    def test_material_and_assessment_removal_is_rejected_for_published_version(self):
        version = CourseVersion.objects.create(course=self.course, version_number=1, status=CourseVersion.Status.DRAFT)
        module = Module.objects.create(course_version=version, title="Getting started", position=1)
        lesson = LessonVersion.objects.create(module=module, title="Welcome", content="Welcome.", position=1)
        artifact = LessonArtifact.objects.create(
            lesson_version=lesson,
            artifact_type=LessonArtifact.ArtifactType.TEXT,
            content="Read this first.",
        )
        question = Question.objects.create(
            lesson_version=lesson,
            question_type=Question.QuestionType.EXPLANATION,
            prompt="Explain the welcome lesson.",
        )
        version.status = CourseVersion.Status.PUBLISHED
        version.save(update_fields=["status"])

        artifact_response = self.client.post(
            reverse(
                "teacher_courses:delete-artifact",
                kwargs={
                    "slug": self.course.slug,
                    "version_id": version.id,
                    "lesson_id": lesson.id,
                    "artifact_id": artifact.id,
                },
            )
        )
        question_response = self.client.post(
            reverse(
                "teacher_courses:delete-question",
                kwargs={
                    "slug": self.course.slug,
                    "version_id": version.id,
                    "lesson_id": lesson.id,
                    "question_id": question.id,
                },
            )
        )
        self.assertEqual(artifact_response.status_code, 403)
        self.assertEqual(question_response.status_code, 403)
        self.assertTrue(LessonArtifact.objects.filter(id=artifact.id).exists())
        self.assertTrue(Question.objects.filter(id=question.id).exists())


class StudentProgressionTests(TestCase):
    def setUp(self):
        self.student = User.objects.create_user(email="progress@example.com", password="StrongPass123!")
        organization = Organization.objects.create(name="Progress School", slug="progress-school")
        Membership.objects.create(organization=organization, user=self.student, role=Membership.Role.STUDENT)
        teacher = User.objects.create_user(email="progress-teacher@example.com", password="StrongPass123!")
        course = Course.objects.create(
            organization=organization,
            created_by=teacher,
            title="Progress Python",
            slug="progress-python",
            status=Course.Status.PUBLISHED,
        )
        Membership.objects.create(organization=organization, user=teacher, role=Membership.Role.TEACHER)
        version = CourseVersion.objects.create(course=course, version_number=1, status=CourseVersion.Status.DRAFT)
        module = Module.objects.create(course_version=version, title="First module", position=1)
        lesson = LessonVersion.objects.create(module=module, title="First lesson", content="Read this.", position=1)
        version.status = CourseVersion.Status.PUBLISHED
        version.save(update_fields=["status"])
        self.course = course
        self.lesson = lesson
        self.enrollment = Enrollment.objects.create(
            course=course,
            course_version=version,
            student=self.student,
        )

    def test_student_can_complete_content_only_lesson(self):
        self.client.force_login(self.student)
        response = self.client.post(
            reverse("courses:complete-lesson", kwargs={"slug": self.course.slug, "lesson_id": self.lesson.id})
        )
        self.assertRedirects(
            response,
            reverse("courses:learn-lesson", kwargs={"slug": self.course.slug, "lesson_id": self.lesson.id}),
        )
        self.assertEqual(self.enrollment.lesson_progress.get().status, "completed")


@override_settings(CELERY_TASK_ALWAYS_EAGER=True, AI_LLM_PROVIDER="fake")
class CourseGenerationTests(TestCase):
    def setUp(self):
        self.teacher = User.objects.create_user(email="generator@example.com", password="StrongPass123!")
        self.organization = Organization.objects.create(name="Generation School", slug="generation-school")
        Membership.objects.create(
            organization=self.organization,
            user=self.teacher,
            role=Membership.Role.TEACHER,
        )
        self.client.force_login(self.teacher)

    def test_generation_form_does_not_preselect_a_location_specific_audience(self):
        response = self.client.get(reverse("teacher_courses:generate"))

        self.assertNotContains(response, 'value="Nigerian secondary-school students"')
        self.assertContains(response, "e.g. Secondary-school learners")

    def test_teacher_generation_creates_reviewable_unpublished_draft(self):
        with self.captureOnCommitCallbacks(execute=True):
            response = self.client.post(
                reverse("teacher_courses:generate"),
                {
                    "title": "Python Problem Solving",
                    "objective": "Learn Python",
                    "duration_weeks": 12,
                    "audience": "Nigerian secondary-school students",
                    "free_prompt": "Use relatable classroom and community examples.",
                },
            )

        generation_request = CourseGenerationRequest.objects.get()
        job = AIJob.objects.get(entity_id=generation_request.id)
        generation_request.refresh_from_db()
        version = generation_request.generated_version

        self.assertRedirects(
            response,
            reverse("teacher_courses:generation-status", kwargs={"request_id": generation_request.id}),
        )
        self.assertEqual(job.status, AIJob.Status.SUCCEEDED)
        self.assertEqual(job.progress, 100)
        self.assertEqual(generation_request.status, CourseGenerationRequest.Status.REVIEW)
        self.assertTrue(version.generated_by_ai)
        self.assertEqual(version.status, CourseVersion.Status.DRAFT)
        self.assertEqual(version.course.status, Course.Status.DRAFT)
        self.assertGreater(version.modules.count(), 0)
        self.assertGreater(version.modules.first().lessons.first().questions.count(), 0)
        self.assertFalse(
            version.modules.first().lessons.first().questions.first().is_objective
        )
        self.assertEqual(version.modules.first().lessons.first().translations.count(), 0)
        self.assertTrue(version.final_project.ai_generated)
        self.assertGreater(len(version.final_project.rubric), 0)
        self.assertFalse(CourseVersion.objects.filter(status=CourseVersion.Status.PUBLISHED).exists())
        self.assertTrue(AuditEvent.objects.filter(action="ai_course_generation_requested").exists())
        self.assertTrue(version.modules.first().lessons.first().artifacts.filter(ai_generated=True, teacher_approved=False).exists())

        publish_response = self.client.post(
            reverse(
                "teacher_courses:publish-version",
                kwargs={"slug": version.course.slug, "version_id": version.id},
            )
        )
        self.assertRedirects(
            publish_response,
            reverse("teacher_courses:studio", kwargs={"slug": version.course.slug}),
        )
        version.refresh_from_db()
        self.assertEqual(version.status, CourseVersion.Status.PUBLISHED)
        self.assertTrue(
            version.modules.first().lessons.first().artifacts.filter(
                ai_generated=True,
                teacher_approved=True,
            ).exists()
        )
        version.final_project.refresh_from_db()
        self.assertTrue(version.final_project.teacher_approved)

        status_response = self.client.get(
            reverse("teacher_courses:generation-status", kwargs={"request_id": generation_request.id})
        )
        self.assertContains(status_response, "Course published and approved.")
        self.assertContains(status_response, "Open course studio")

    def test_generation_form_omits_translation_languages(self):
        response = self.client.get(reverse("teacher_courses:generate"))

        self.assertNotContains(response, "Translation languages")

    def test_teacher_can_create_and_edit_a_manual_final_project(self):
        course = Course.objects.create(
            organization=self.organization,
            created_by=self.teacher,
            title="Manual project course",
            slug="manual-project-course",
        )
        version = CourseVersion.objects.create(course=course, version_number=1, status=CourseVersion.Status.DRAFT)
        response = self.client.post(
            reverse(
                "teacher_courses:final-project",
                kwargs={"slug": course.slug, "version_id": version.id},
            ),
            {
                "title": "School attendance tracker",
                "brief": "Build a small Python program that helps a school club record and summarize attendance.",
                "estimated_hours": 8,
                "objectives_text": "Plan a practical program\nApply Python fundamentals",
                "requirements_text": "Use input and output\nInclude a conditional",
                "deliverables_text": "Python source code\nTest evidence",
                "rubric_text": "Solves the stated problem\nExplains testing",
            },
        )
        self.assertRedirects(
            response,
            reverse("teacher_courses:version-editor", kwargs={"slug": course.slug, "version_id": version.id}),
        )
        project = FinalProject.objects.get(course_version=version)
        self.assertFalse(project.ai_generated)
        self.assertEqual(project.objectives, ["Plan a practical program", "Apply Python fundamentals"])
        self.assertEqual(len(project.rubric), 2)

    def test_student_cannot_view_another_users_generation_status(self):
        student = User.objects.create_user(email="generation-student@example.com", password="StrongPass123!")
        generation_request = CourseGenerationRequest.objects.create(
            created_by=self.teacher,
            course=Course.objects.create(
                organization=self.organization,
                created_by=self.teacher,
                title="Private generated course",
            ),
            title="Private generated course",
        )
        self.client.force_login(student)
        response = self.client.get(
            reverse("teacher_courses:generation-status", kwargs={"request_id": generation_request.id})
        )
        self.assertEqual(response.status_code, 404)

    def test_generation_preserves_an_existing_manual_draft(self):
        course = Course.objects.create(
            organization=self.organization,
            created_by=self.teacher,
            title="Existing Manual Course",
        )
        manual_version = CourseVersion.objects.create(course=course, version_number=1, status=CourseVersion.Status.DRAFT)
        Module.objects.create(course_version=manual_version, title="Manual module", position=1)
        request = CourseGenerationRequest.objects.create(
            created_by=self.teacher,
            course=course,
            title=course.title,
            objective="Learn Python",
            duration_weeks=4,
            audience="Secondary students",
        )
        job = AIJob.objects.create(
            job_type=AIJob.JobType.COURSE_GENERATION,
            entity_type="course_generation_request",
            entity_id=request.id,
        )

        from ai_engine.tasks import generate_course

        generate_course.apply(args=[str(job.id)]).get()
        request.refresh_from_db()
        self.assertEqual(request.generated_version.version_number, 2)
        self.assertEqual(manual_version.modules.get().title, "Manual module")
        self.assertGreater(request.generated_version.modules.count(), 0)
