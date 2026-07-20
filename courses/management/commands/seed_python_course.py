import os

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from accounts.models import User
from assessments.models import Question, RubricVersion
from courses.models import Course, CourseVersion, LessonVersion, Module
from enrollments.models import Enrollment
from organizations.models import Membership, Organization


COURSE_SLUG = "python-fundamentals"
TEACHER_EMAIL = "teacher@aiducator.local"
STUDENT_EMAIL = "student@aiducator.local"
DEFAULT_PASSWORD = "Aiducator123!"

MODULES = [
    (
        "Algorithms and Python setup",
        "Algorithms are step-by-step instructions for solving problems. Python lets us express those instructions clearly.",
        ["Describe an algorithm", "Write and run a simple Python program"],
        "What is an algorithm, and how can Python be used to express one?",
    ),
    (
        "Variables and data types",
        "Variables give names to values. Python commonly works with strings, integers, floats, and booleans.",
        ["Create variables", "Identify common Python data types"],
        "Explain what a variable is and give two examples of Python data types.",
    ),
    (
        "Input, output, and operators",
        "The input function receives text from a user, print displays output, and operators let us calculate and compare values.",
        ["Read user input", "Use arithmetic and comparison operators"],
        "Explain how input, print, and an arithmetic operator work together in a Python program.",
    ),
    (
        "Conditional statements",
        "Conditional statements allow a program to choose different actions based on whether a condition is true or false.",
        ["Write if statements", "Use elif and else branches"],
        "Describe when a Python program should use an if statement and provide a simple example.",
    ),
    (
        "For and while loops",
        "Loops repeat instructions. A for loop is useful for iterating over items, while a while loop repeats while a condition remains true.",
        ["Use for loops", "Use while loops safely"],
        "Explain one difference between a for loop and a while loop.",
    ),
    (
        "Functions and parameters",
        "Functions package reusable instructions. Parameters allow a function to receive data and return can send a result back.",
        ["Define functions", "Pass arguments and return values"],
        "Why are functions useful? Explain the roles of a parameter and a return value.",
    ),
    (
        "Strings and string methods",
        "Strings store text. Python provides methods for changing, searching, splitting, and combining strings.",
        ["Work with string values", "Use common string methods"],
        "Explain how a Python program can find or change part of a string.",
    ),
    (
        "Lists, tuples, dictionaries, and sets",
        "Collections store groups of values. Each collection type has different rules for ordering, changing, and finding items.",
        ["Choose an appropriate collection", "Access and update collection values"],
        "Give one appropriate use for a list and one appropriate use for a dictionary.",
    ),
    (
        "Debugging and common errors",
        "Debugging is the process of finding and fixing problems. Syntax, runtime, and logic errors require different approaches.",
        ["Recognize common errors", "Use a systematic debugging process"],
        "Explain the difference between a syntax error and a logic error.",
    ),
    (
        "Files, modules, and code organization",
        "Programs can read and write files and reuse code from modules. Good organization makes programs easier to understand and maintain.",
        ["Describe file operations", "Explain why modules are useful"],
        "Why should a Python program close a file after it finishes using it?",
    ),
    (
        "Mini-project development",
        "A project combines planning, implementation, testing, and explanation to solve a small real-world problem.",
        ["Plan a small Python project", "Explain implementation decisions"],
        "Describe the problem your Python mini-project will solve and the steps you will take.",
    ),
    (
        "Revision and final assessment",
        "Revision connects the core concepts and prepares learners to explain and apply Python fundamentals independently.",
        ["Connect Python fundamentals", "Apply Python to a new problem"],
        "Choose a Python fundamental and explain how it helps solve a practical problem.",
    ),
]


class Command(BaseCommand):
    help = "Seed the Aiducator Nigerian secondary-school Python fundamentals course."

    @transaction.atomic
    def handle(self, *args, **options):
        organization, _ = Organization.objects.get_or_create(
            slug="aiducator-pilot-school",
            defaults={"name": "Aiducator Pilot School"},
        )

        teacher, teacher_created = User.objects.get_or_create(
            email=TEACHER_EMAIL,
            defaults={
                "first_name": "Python",
                "last_name": "Teacher",
                "is_active": True,
            },
        )
        if teacher_created:
            teacher.set_password(os.environ.get("AIDUCATOR_SEED_PASSWORD", DEFAULT_PASSWORD))
            teacher.save(update_fields=["password"])

        student, student_created = User.objects.get_or_create(
            email=STUDENT_EMAIL,
            defaults={
                "first_name": "Python",
                "last_name": "Student",
                "is_active": True,
            },
        )
        if student_created:
            student.set_password(os.environ.get("AIDUCATOR_SEED_PASSWORD", DEFAULT_PASSWORD))
            student.save(update_fields=["password"])

        Membership.objects.update_or_create(
            organization=organization,
            user=teacher,
            defaults={"role": Membership.Role.TEACHER},
        )
        Membership.objects.update_or_create(
            organization=organization,
            user=student,
            defaults={"role": Membership.Role.STUDENT},
        )

        course, _ = Course.objects.update_or_create(
            slug=COURSE_SLUG,
            defaults={
                "organization": organization,
                "created_by": teacher,
                "title": "Python Fundamentals",
                "description": "A 12-week introduction to Python programming for Nigerian secondary-school students.",
                "duration_weeks": 12,
                "passing_score": 70,
                "max_retries": 2,
                "status": Course.Status.PUBLISHED,
            },
        )
        version, version_created = CourseVersion.objects.get_or_create(
            course=course,
            version_number=1,
            defaults={
                "status": CourseVersion.Status.DRAFT,
                "generated_by_ai": False,
            },
        )

        if version_created or version.status != CourseVersion.Status.PUBLISHED:
            for position, (title, content, objectives, prompt) in enumerate(MODULES, start=1):
                module, _ = Module.objects.update_or_create(
                    course_version=version,
                    position=position,
                    defaults={"title": title},
                )
                lesson, _ = LessonVersion.objects.update_or_create(
                    module=module,
                    position=1,
                    defaults={
                        "title": f"{title}: foundations",
                        "objectives": objectives,
                        "content": content,
                        "status": LessonVersion.Status.DRAFT,
                    },
                )
                question, _ = Question.objects.update_or_create(
                    lesson_version=lesson,
                    position=1,
                    defaults={
                        "question_type": Question.QuestionType.SCENARIO,
                        "prompt": prompt,
                        "max_score": 100,
                        "is_active": True,
                        "is_objective": False,
                    },
                )
                RubricVersion.objects.update_or_create(
                    question=question,
                    version_number=1,
                    defaults={
                        "criteria": [
                            {
                                "criterion": "Uses accurate Python terminology",
                                "weight": 30,
                            },
                            {
                                "criterion": "Explains the concept clearly with a relevant example",
                                "weight": 50,
                            },
                            {
                                "criterion": "Connects the concept to practical problem solving",
                                "weight": 20,
                            },
                        ],
                        "total_score": 100,
                        "approved_by": teacher,
                        "approved_at": timezone.now(),
                    },
                )

            LessonVersion.objects.filter(module__course_version=version).update(status=LessonVersion.Status.PUBLISHED)
            version.status = CourseVersion.Status.PUBLISHED
            version.approved_by = teacher
            version.approved_at = timezone.now()
            version.save(update_fields=["status", "approved_by", "approved_at"])

        enrollment, _ = Enrollment.objects.update_or_create(
            course=course,
            student=student,
            defaults={
                "course_version": version,
                "status": Enrollment.Status.ACTIVE,
            },
        )

        self.stdout.write(self.style.SUCCESS("Aiducator Python course seeded successfully."))
        self.stdout.write(f"Organization: {organization.name} ({organization.slug})")
        self.stdout.write(f"Teacher: {teacher.email}")
        self.stdout.write(f"Student: {student.email}")
        self.stdout.write(f"Seed password for new accounts: {os.environ.get('AIDUCATOR_SEED_PASSWORD', DEFAULT_PASSWORD)}")
        self.stdout.write(f"Course: {course.title} ({course.slug})")
        self.stdout.write(f"Modules: {len(MODULES)}")
        self.stdout.write(f"Enrollment: {enrollment.student.email} → {enrollment.course.title}")
