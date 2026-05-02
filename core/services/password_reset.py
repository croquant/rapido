import logging

from django.conf import settings
from django.db import transaction
from django.urls import reverse

from core.models import OrganizationMembership, Role, User
from core.services.mail import send_templated
from core.services.tokens import RESET_SALT, make_token

logger = logging.getLogger(__name__)


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
    token = make_token(user, salt=RESET_SALT)
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
