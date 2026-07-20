from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from django.utils import timezone

from .models import Notification


@login_required
def inbox(request):
    notifications = Notification.objects.filter(recipient=request.user)
    notifications.filter(read_at__isnull=True).update(read_at=timezone.now())
    return render(request, "notifications/inbox.html", {"notifications": notifications})
