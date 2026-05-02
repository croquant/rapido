from typing import Any

from django.core import signing

from core.models import Invitation, User

VERIFY_SALT = "verify-email"
RESET_SALT = "password-reset"
INVITE_SALT = "invite"

VERIFY_MAX_AGE = 7 * 24 * 3600
RESET_MAX_AGE = 3600
INVITE_MAX_AGE = 7 * 24 * 3600


def make_token(user: User, *, salt: str) -> str:
    return signing.dumps({"user_id": user.pk}, salt=salt)


def verify_token(token: str, *, salt: str, max_age: int) -> dict[str, Any]:
    return signing.loads(token, salt=salt, max_age=max_age)


def make_invite_token(invitation: Invitation) -> str:
    return signing.dumps({"invitation_id": invitation.pk}, salt=INVITE_SALT)


def verify_invite_token(token: str) -> dict[str, Any]:
    return signing.loads(token, salt=INVITE_SALT, max_age=INVITE_MAX_AGE)
