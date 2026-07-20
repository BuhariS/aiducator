from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("ai_engine", "0003_alter_aijob_job_type")]

    operations = [
        migrations.AddField(
            model_name="coursegenerationrequest",
            name="assessment_types",
            field=models.JSONField(blank=True, default=list),
        ),
    ]
