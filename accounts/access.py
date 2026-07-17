from organizations.models import Membership


TEACHER_ROLES = {
    Membership.Role.OWNER,
    Membership.Role.ADMIN,
    Membership.Role.TEACHER,
}


def user_has_teacher_access(user, organization):
    return user.is_superuser or Membership.objects.filter(
        user=user,
        organization=organization,
        role__in=TEACHER_ROLES,
    ).exists()
