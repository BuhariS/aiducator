from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("courses", "0003_lessonartifact_asset"),
    ]

    operations = [
        migrations.CreateModel(
            name="Lesson",
            fields=[],
            options={
                "verbose_name": "Lesson",
                "verbose_name_plural": "Lessons",
                "proxy": True,
                "indexes": [],
                "constraints": [],
            },
            bases=("courses.lessonversion",),
        ),
    ]
