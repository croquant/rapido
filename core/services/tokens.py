from typing import Any

from django.core import signing

from core.models import User

VERIFY_SALT = "verify-email"
RESET_SALT = "password-reset"
INVITE_SALT = "invite"

VERIFY_MAX_AGE = 7 * 24 * 3600
RESET_MAX_AGE = 3600


def make_token(user: User, *, salt: str) -> str:
    return signing.dumps({"user_id": user.pk}, salt=salt)


def verify_token(token: str, *, salt: str, max_age: int) -> dict[str, Any]:
    return signing.loads(token, salt=salt, max_age=max_age)
