from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("assessments", "0006_alter_attempt_answer_text_and_more")]

    operations = [
        migrations.AlterField(
            model_name="question",
            name="question_type",
            field=models.CharField(
                choices=[
                    ("reflection", "Reflection"),
                    ("scenario", "Scenario-based"),
                    ("critical_thinking", "Critical thinking"),
                    ("task_prompt", "Task prompt generation"),
                    ("misconception", "Common misconception"),
                ],
                max_length=20,
            ),
        ),
    ]
