from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("enrollments", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="StudentProgress",
            fields=[],
            options={
                "verbose_name": "Student progress",
                "verbose_name_plural": "Student progress",
                "proxy": True,
                "indexes": [],
                "constraints": [],
            },
            bases=("enrollments.lessonprogress",),
        ),
    ]
