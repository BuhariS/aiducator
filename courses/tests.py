from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse

from ai_engine.models import AIJob, CourseGenerationRequest
from accounts.models import User
from enrollments.models import Enrollment
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

    def test_module_and_lesson_forms_continue_to_next_step(self):
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
                "objectives_text": "Explain variables",
                "content": "A variable gives a name to a value in a Python program.",
                "next": "question",
            },
        )
        lesson = LessonVersion.objects.get(module=module)
        self.assertRedirects(
            response,
            reverse(
                "teacher_courses:create-question",
                kwargs={"slug": self.course.slug, "version_id": version.id, "lesson_id": lesson.id},
            ),
        )

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
        self.assertRedirects(
            response,
            reverse("teacher_courses:version-editor", kwargs={"slug": self.course.slug, "version_id": version.id}),
        )
        self.assertTrue(LessonArtifact.objects.filter(lesson_version=lesson, artifact_type="image").exists())
        response = self.client.get(
            reverse("teacher_courses:preview-version", kwargs={"slug": self.course.slug, "version_id": version.id})
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Welcome")


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

    def test_teacher_generation_creates_reviewable_unpublished_draft(self):
        with self.captureOnCommitCallbacks(execute=True):
            response = self.client.post(
                reverse("teacher_courses:generate"),
                {
                    "title": "Python Problem Solving",
                    "objective": "Learn Python",
                    "duration_weeks": 12,
                    "audience": "Nigerian secondary-school students",
                    "translation_languages": "yo-NG, ha-NG",
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
        self.assertEqual(version.modules.first().lessons.first().translations.count(), 2)
        self.assertTrue(version.final_project.ai_generated)
        self.assertGreater(len(version.final_project.rubric), 0)
        self.assertFalse(CourseVersion.objects.filter(status=CourseVersion.Status.PUBLISHED).exists())

        status_response = self.client.get(
            reverse("teacher_courses:generation-status", kwargs={"request_id": generation_request.id})
        )
        self.assertContains(status_response, "Draft ready for teacher review.")
        self.assertContains(status_response, "Review draft in Course Studio")

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
