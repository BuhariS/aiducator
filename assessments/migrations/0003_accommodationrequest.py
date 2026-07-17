import uuid

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("assessments", "0002_aigrade_ai_score_range_aigrade_ai_confidence_range"),
        ("courses", "0003_lessonartifact_asset"),
    ]

    operations = [
        migrations.CreateModel(
            name="AccommodationRequest",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("accommodation_type", models.CharField(choices=[("copy_paste", "Copy and paste assistance"), ("extended_time", "Extended assessment time"), ("screen_reader", "Screen reader support"), ("other", "Other accommodation")], max_length=30)),
                ("details", models.TextField()),
                ("status", models.CharField(choices=[("pending", "Pending"), ("approved", "Approved"), ("declined", "Declined")], default="pending", max_length=20)),
                ("reviewed_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("course", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="accommodation_requests", to="courses.course")),
                ("reviewed_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="reviewed_accommodations", to=settings.AUTH_USER_MODEL)),
                ("student", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="accommodation_requests", to=settings.AUTH_USER_MODEL)),
            ],
        ),
    ]
