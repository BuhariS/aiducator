from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse

from accounts.models import User
from enrollments.models import Enrollment
from organizations.models import Membership, Organization

from .models import Course, CourseVersion, LessonArtifact, LessonVersion, Module


class CourseFlowTests(TestCase):
    def setUp(self):
        self.student = User.objects.create_user(email="student@example.com", password="StrongPass123!")
        self.organization = Organization.objects.create(name="AIDUCATOR Pilot", slug="aiducator-pilot")
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
