from .models import AccommodationRequest


def has_copy_paste_accommodation(student, course):
    return AccommodationRequest.objects.filter(
        student=student,
        course=course,
        accommodation_type=AccommodationRequest.AccommodationType.COPY_PASTE,
        status=AccommodationRequest.Status.APPROVED,
    ).exists()
