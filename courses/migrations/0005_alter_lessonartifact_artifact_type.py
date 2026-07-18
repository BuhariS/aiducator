from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("courses", "0004_lesson")]

    operations = [
        migrations.AlterField(
            model_name="lessonartifact",
            name="artifact_type",
            field=models.CharField(
                choices=[
                    ("text", "Text"),
                    ("video_embed", "Video embed"),
                    ("image", "Image"),
                    ("simulation_link", "Simulation link"),
                    ("code_example", "Code example"),
                    ("image_prompt", "Image prompt"),
                    ("youtube_search", "YouTube search suggestion"),
                ],
                max_length=30,
            ),
        ),
    ]
