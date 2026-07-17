from django.urls import path

from .views import attempt_status, review_detail, review_queue, submit_attempt

app_name = "assessments"

urlpatterns = [
    path("questions/<uuid:question_id>/submit/", submit_attempt, name="submit"),
    path("attempts/<uuid:attempt_id>/status/", attempt_status, name="attempt-status"),
    path("reviews/", review_queue, name="review-queue"),
    path("reviews/<uuid:review_id>/", review_detail, name="review-detail"),
]
