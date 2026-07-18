from django.core.management.base import BaseCommand

from assessments.models import Attempt, Submission


class Command(BaseCommand):
    help = "Encrypt existing assessment answers using AI_FIELD_ENCRYPTION_KEY."

    def handle(self, *args, **options):
        attempts = 0
        submissions = 0
        for attempt in Attempt.objects.iterator():
            attempt.save(update_fields=["answer_text"])
            attempts += 1
        for submission in Submission.objects.iterator():
            submission.save(update_fields=["answer_text"])
            submissions += 1
        self.stdout.write(
            self.style.SUCCESS(
                f"Re-encrypted {attempts} attempt answers and {submissions} submission answers."
            )
        )
