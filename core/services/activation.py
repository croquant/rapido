from django.db import transaction

from core.models import OrganizationMembership, Role, User
from core.services.exceptions import (
    AlreadyActiveError,
    NoAdminMembershipError,
)
from core.services.tokens import VERIFY_MAX_AGE, VERIFY_SALT, verify_token


def activate_from_token(token: str) -> User:
    payload = verify_token(token, salt=VERIFY_SALT, max_age=VERIFY_MAX_AGE)
    user_id = payload["user_id"]
    with transaction.atomic():
        user = User.objects.select_for_update().get(pk=user_id)
        if user.is_active:
            raise AlreadyActiveError
        mem = (
            OrganizationMembership.objects.select_for_update()
            .select_related("organization")
            .filter(user=user, role=Role.ADMIN, is_active=True)
            .order_by("created_at")
            .first()
        )
        if mem is None:
            raise NoAdminMembershipError
        user.is_active = True
        user.save()
        org = mem.organization
        org.is_active = True
        org.save()
        return user
