from django.urls import path

from .views import (
    accommodation_queue,
    accommodation_requested,
    decide_accommodation,
    request_accommodation,
    attempt_status,
    review_detail,
    review_queue,
    submit_attempt,
)

app_name = "assessments"

urlpatterns = [
    path("questions/<uuid:question_id>/submit/", submit_attempt, name="submit"),
    path("accommodations/request/", request_accommodation, name="request-accommodation"),
    path("accommodations/requested/", accommodation_requested, name="accommodation-requested"),
    path("accommodations/", accommodation_queue, name="accommodation-queue"),
    path("accommodations/<uuid:request_id>/decision/", decide_accommodation, name="decide-accommodation"),
    path("attempts/<uuid:attempt_id>/status/", attempt_status, name="attempt-status"),
    path("reviews/", review_queue, name="review-queue"),
    path("reviews/<uuid:review_id>/", review_detail, name="review-detail"),
]
