from django.conf import settings
from django.db import transaction
from django.urls import reverse

from core.models import OrganizationMembership, Role, User
from core.services.mail import send_templated
from core.services.tokens import VERIFY_SALT, make_token


def resend_verification_email(email: str) -> None:
    # Idempotent: looks up an inactive user by case-insensitive email and
    # enqueues a fresh verify email on commit. No-op for active, missing,
    # or empty inputs so the caller can always render the same "sent"
    # response without enumerating accounts (whitepaper epic 2b §3).
    if not email:
        return
    user = User.objects.filter(email__iexact=email, is_active=False).first()
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
    org_name = mem.organization.name if mem else ""
    language = mem.organization.default_language if mem else None
    token = make_token(user, salt=VERIFY_SALT)
    verify_url = f"{settings.SITE_URL}{reverse('core:verify', args=[token])}"
    transaction.on_commit(
        lambda: send_templated(
            "email/verify",
            to=user,
            language=language,
            context={"verify_url": verify_url, "org_name": org_name},
        )
    )
