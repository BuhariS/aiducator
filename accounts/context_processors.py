from .access import user_is_teacher


def user_role_flags(request):
    return {
        "is_teacher": bool(request.user.is_authenticated and user_is_teacher(request.user)),
    }
