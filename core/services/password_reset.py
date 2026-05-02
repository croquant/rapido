import hashlib
import logging

from django.conf import settings
from django.core import signing
from django.db import transaction
from django.urls import reverse

from core.models import OrganizationMembership, Role, User
from core.services.mail import send_templated
from core.services.tokens import RESET_MAX_AGE, RESET_SALT

logger = logging.getLogger(__name__)


def _password_fingerprint(user: User) -> str:
    # Short SHA-256 prefix of the password hash. Embedded in the signed
    # token so a successful reset invalidates the prior link: once
    # set_password() runs, the stored hash changes and the token's
    # fingerprint no longer matches. Keeps replay-after-success out of
    # the 1h window without persisting per-token state.
    return hashlib.sha256(user.password.encode()).hexdigest()[:16]


def make_password_reset_token(user: User) -> str:
    return signing.dumps(
        {"user_id": user.pk, "pwf": _password_fingerprint(user)},
        salt=RESET_SALT,
    )


def verify_password_reset_token(token: str) -> User:
    # Raises signing.BadSignature (incl. SignatureExpired) on bad/expired
    # tokens, on inactive users, and on fingerprint mismatch (the password
    # has been rotated since the token was issued).
    payload = signing.loads(token, salt=RESET_SALT, max_age=RESET_MAX_AGE)
    user = User.objects.filter(
        pk=payload.get("user_id"), is_active=True
    ).first()
    if user is None or _password_fingerprint(user) != payload.get("pwf"):
        raise signing.BadSignature("password reset token no longer valid")
    return user


def _send_reset_email(
    *, user: User, language: str | None, reset_url: str
) -> None:
    # Best-effort. Swallowing keeps the request view non-enumerating: an
    # SMTP / template failure on a real account must not turn the
    # active-user branch into a 500 while missing/inactive return 200.
    try:
        send_templated(
            "email/password_reset",
            to=user,
            language=language,
            context={"reset_url": reset_url},
        )
    except Exception:
        logger.exception("password reset email failed for user_id=%s", user.pk)


def request_password_reset_email(email: str) -> None:
    # Idempotent: looks up an active user by case-insensitive email and
    # enqueues a reset email on commit. No-op for missing, inactive, or
    # empty inputs so the caller can always render the same "sent"
    # response without enumerating accounts (whitepaper epic 2b §4).
    if not email:
        return
    user = User.objects.filter(email__iexact=email, is_active=True).first()
    if user is None:
        return
    mem = (
        OrganizationMembership.objects.filter(
            user=user, role=Role.ADMIN, is_active=True
        )
        .select_related("organization")
        .order_by("created_at")
        .first()
    )
    language = mem.organization.default_language if mem else None
    token = make_password_reset_token(user)
    reset_url = (
        f"{settings.SITE_URL}"
        f"{reverse('core:password_reset_confirm', args=[token])}"
    )
    transaction.on_commit(
        lambda: _send_reset_email(
            user=user,
            language=language,
            reset_url=reset_url,
        )
    )
