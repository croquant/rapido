from typing import cast

from django.conf import settings
from django.contrib.auth import update_session_auth_hash
from django.contrib.auth.password_validation import validate_password
from django.contrib.sessions.models import Session
from django.core.exceptions import ValidationError as DjangoValidationError
from django.http import HttpRequest
from django.utils import timezone

from core.models import User
from core.services.exceptions import WeakPasswordError, WrongPasswordError


def update_profile(
    user: User,
    *,
    first_name: str,
    last_name: str,
    preferred_language: str,
) -> User:
    if preferred_language and preferred_language not in dict(
        settings.LANGUAGES
    ):
        raise DjangoValidationError(
            {"preferred_language": "Unsupported language."}
        )
    user.first_name = first_name
    user.last_name = last_name
    user.preferred_language = preferred_language
    user.save(
        update_fields=[
            "first_name",
            "last_name",
            "preferred_language",
            "updated_at",
        ]
    )
    return user


def change_password(
    request: HttpRequest,
    *,
    current_password: str,
    new_password: str,
) -> None:
    user = cast(User, request.user)
    if not user.check_password(current_password):
        raise WrongPasswordError("current password did not match")
    try:
        validate_password(new_password, user=user)
    except DjangoValidationError as exc:
        raise WeakPasswordError(list(exc.messages)) from exc
    user.set_password(new_password)
    user.save(update_fields=["password", "updated_at"])
    update_session_auth_hash(request, user)
    _invalidate_other_sessions(
        user_pk=user.pk, keep=request.session.session_key
    )


def _invalidate_other_sessions(*, user_pk: int, keep: str | None) -> None:
    user_pk_str = str(user_pk)
    for session in Session.objects.filter(expire_date__gte=timezone.now()):
        if session.session_key == keep:
            continue
        if session.get_decoded().get("_auth_user_id") == user_pk_str:
            session.delete()
