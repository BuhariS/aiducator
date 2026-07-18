from django.urls import path

from .views import (
    accommodation_queue,
    accommodation_requested,
    decide_accommodation,
    decide_appeal,
    appeal_queue,
    request_accommodation,
    submit_appeal,
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
    path("attempts/<uuid:attempt_id>/appeal/", submit_appeal, name="submit-appeal"),
    path("reviews/", review_queue, name="review-queue"),
    path("reviews/<uuid:review_id>/", review_detail, name="review-detail"),
    path("appeals/", appeal_queue, name="appeal-queue"),
    path("appeals/<uuid:appeal_id>/decision/", decide_appeal, name="decide-appeal"),
]
