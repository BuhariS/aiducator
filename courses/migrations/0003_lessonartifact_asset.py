from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("courses", "0002_alter_course_slug"),
    ]

    operations = [
        migrations.AddField(
            model_name="lessonartifact",
            name="asset",
            field=models.FileField(blank=True, upload_to="lesson-artifacts/"),
        ),
    ]
