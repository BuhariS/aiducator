import django.db.models.deletion
import uuid
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("courses", "0004_lesson"),
        ("ai_engine", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="aijob",
            name="error_details",
            field=models.JSONField(blank=True, default=dict),
        ),
        migrations.AddField(
            model_name="aijob",
            name="estimated_cost",
            field=models.DecimalField(decimal_places=6, default=0, max_digits=12),
        ),
        migrations.AddField(
            model_name="aijob",
            name="input_tokens",
            field=models.PositiveIntegerField(default=0),
        ),
        migrations.AddField(
            model_name="aijob",
            name="output_tokens",
            field=models.PositiveIntegerField(default=0),
        ),
        migrations.CreateModel(
            name="CourseGenerationRequest",
            fields=[
                (
                    "id",
                    models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False),
                ),
                ("title", models.CharField(max_length=180)),
                ("objective", models.TextField(blank=True)),
                ("duration_weeks", models.PositiveSmallIntegerField(default=12)),
                ("audience", models.CharField(blank=True, max_length=180)),
                ("free_prompt", models.TextField(blank=True)),
                ("translation_languages", models.JSONField(blank=True, default=list)),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("queued", "Queued"),
                            ("running", "Running"),
                            ("review", "Ready for teacher review"),
                            ("failed", "Failed"),
                            ("published", "Published"),
                        ],
                        default="queued",
                        max_length=20,
                    ),
                ),
                ("error_details", models.JSONField(blank=True, default=dict)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("completed_at", models.DateTimeField(blank=True, null=True)),
                (
                    "course",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="generation_requests",
                        to="courses.course",
                    ),
                ),
                (
                    "created_by",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="course_generation_requests",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "generated_version",
                    models.OneToOneField(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="generation_request",
                        to="courses.courseversion",
                    ),
                ),
            ],
            options={"ordering": ["-created_at"]},
        ),
    ]
