from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("assessments", "0003_accommodationrequest")]

    operations = [
        migrations.AlterField(
            model_name="question",
            name="question_type",
            field=models.CharField(
                choices=[
                    ("explanation", "Explanation"),
                    ("code_writing", "Code writing"),
                    ("debugging", "Debugging"),
                    ("reflection", "Reflection"),
                    ("scenario", "Scenario-based"),
                    ("critical_thinking", "Critical thinking"),
                    ("task_prompt", "Task prompt generation"),
                    ("misconception", "Common misconception"),
                    ("error_identification", "Identify the mistakes"),
                ],
                max_length=20,
            ),
        ),
    ]
