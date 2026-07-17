from organizations.models import Membership


TEACHER_ROLES = {
    Membership.Role.OWNER,
    Membership.Role.ADMIN,
    Membership.Role.TEACHER,
}

ADMIN_ROLES = {
    Membership.Role.OWNER,
    Membership.Role.ADMIN,
}

STUDENT_ROLES = {
    Membership.Role.STUDENT,
}


def user_has_any_role(user, roles):
    return bool(
        user
        and user.is_authenticated
        and Membership.objects.filter(user=user, role__in=roles).exists()
    )


def user_has_teacher_access(user, organization):
    return user.is_superuser or Membership.objects.filter(
        user=user,
        organization=organization,
        role__in=TEACHER_ROLES,
    ).exists()


def user_has_admin_access(user, organization=None):
    if user.is_superuser:
        return True
    memberships = Membership.objects.filter(user=user, role__in=ADMIN_ROLES)
    if organization is not None:
        memberships = memberships.filter(organization=organization)
    return memberships.exists()


def user_is_teacher(user):
    return user.is_superuser or user_has_any_role(user, TEACHER_ROLES)


def user_is_student(user):
    return user_has_any_role(user, STUDENT_ROLES)
