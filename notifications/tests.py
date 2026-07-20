from django.test import TestCase
from django.urls import reverse

from accounts.models import User

from .models import Notification


class NotificationInboxTests(TestCase):
    def test_unread_badge_clears_when_inbox_is_opened(self):
        user = User.objects.create_user(email="learner@example.com", password="StrongPass123!")
        Notification.objects.create(
            recipient=user,
            notification_type="project_reviewed",
            title="Your project was reviewed",
            body="Your project feedback is ready.",
        )
        self.client.force_login(user)

        response = self.client.get(reverse("courses:catalog"))
        self.assertContains(response, 'aria-label="1 unread notifications"')

        response = self.client.get(reverse("notifications:inbox"))
        self.assertNotContains(response, 'aria-label="1 unread notifications"')
        self.assertIsNotNone(Notification.objects.get(recipient=user).read_at)
