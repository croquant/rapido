import logging
from collections.abc import Iterable
from datetime import timedelta

from django.conf import settings
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from django.core.signing import BadSignature, SignatureExpired
from django.db import IntegrityError, transaction
from django.utils import timezone

from core.models import (
    Invitation,
    Location,
    LocationMembership,
    Organization,
    OrganizationMembership,
    Role,
    User,
)
from core.services.exceptions import (
    AlreadyMemberError,
    BadStateError,
    OperatorRequiresLocationsError,
    WeakPasswordError,
)
from core.services.mail import send_templated
from core.services.tokens import make_invite_token, verify_invite_token

logger = logging.getLogger(__name__)

INVITE_TTL = timedelta(days=7)


def _send_invitation_email(invitation: Invitation) -> None:
    # Best-effort: invitation has already committed. Log and swallow so SMTP
    # or template errors don't masquerade as a failed create/resend; admin
    # can resend from the pending list.
    try:
        existing = (
            User.objects.filter(email__iexact=invitation.email)
            .only("email", "preferred_language")
            .first()
        )
        org_lang = invitation.organization.default_language
        if existing is None:
            # Unsaved User just to satisfy send_templated's `to: User`
            # contract (it reads `email` and `preferred_language` only).
            addressee = User(
                email=invitation.email, preferred_language=org_lang
            )
            language = org_lang
        else:
            # Epic 2c §6: existing user's preferred_language wins; fall back
            # to the org default when blank.
            addressee = existing
            language = existing.preferred_language or org_lang
        token = make_invite_token(invitation)
        accept_url = f"{settings.SITE_URL}/invite/{token}/"
        inviter = invitation.created_by
        inviter_name = (
            f"{inviter.first_name} {inviter.last_name}".strip() or inviter.email
        )
        send_templated(
            "email/invitation",
            to=addressee,
            language=language,
            context={
                "invitee_email": invitation.email,
                "inviter_name": inviter_name,
                "organization_name": invitation.organization.name,
                "role": invitation.role,
                "locations": list(invitation.locations.all()),
                "accept_url": accept_url,
                "expires_at": invitation.expires_at,
            },
        )
    except Exception:
        logger.exception(
            "invitation email send failed for invitation_id=%s", invitation.pk
        )


def create_invitation(
    *,
    organization: Organization,
    email: str,
    role: str,
    locations: Iterable[Location] = (),
    created_by: User,
) -> Invitation:
    email = email.lower()
    if OrganizationMembership.objects.filter(
        user__email__iexact=email,
        organization=organization,
        is_active=True,
    ).exists():
        raise AlreadyMemberError(email, organization)

    locs = list(locations)

    if role == Role.OPERATOR and not locs:
        raise OperatorRequiresLocationsError()

    if locs:
        bad = [
            loc
            for loc in locs
            if loc.organization.pk != organization.pk or not loc.is_active
        ]
        if bad:
            slugs = ", ".join(sorted(loc.slug for loc in bad))
            raise OperatorRequiresLocationsError(
                f"Invalid or inactive locations: {slugs}"
            )

    with transaction.atomic():
        try:
            invitation = Invitation.objects.create(
                organization=organization,
                email=email,
                role=role,
                created_by=created_by,
                expires_at=timezone.now() + INVITE_TTL,
            )
        except IntegrityError as exc:
            raise BadStateError("pending_exists") from exc
        if locs:
            invitation.locations.set(locs)
        transaction.on_commit(lambda: _send_invitation_email(invitation))
        return invitation


def _sync_location_memberships(
    *,
    user: User,
    invitation: Invitation,
) -> None:
    for loc in invitation.locations.all():
        LocationMembership.objects.update_or_create(
            user=user,
            location=loc,
            defaults={
                "is_active": True,
                "created_by": invitation.created_by,
            },
        )


def accept_invitation(token: str, *, password: str | None = None) -> User:
    try:
        payload = verify_invite_token(token)
    except (BadSignature, SignatureExpired) as exc:
        raise BadStateError("invalid_token") from exc

    invitation_id = payload.get("invitation_id")
    if not invitation_id:
        raise BadStateError("invalid_token")

    with transaction.atomic():
        invitation = (
            Invitation.objects.select_for_update()
            .select_related("organization")
            .get(pk=invitation_id)
        )
        if invitation.accepted_at is not None:
            raise BadStateError("already_accepted")
        if invitation.revoked_at is not None:
            raise BadStateError("already_revoked")
        if invitation.expires_at < timezone.now():
            raise BadStateError("expired")

        invite_locations = list(invitation.locations.all())
        stale = [loc for loc in invite_locations if not loc.is_active]
        if stale:
            raise BadStateError("stale_locations")

        existing = User.objects.filter(email__iexact=invitation.email).first()

        if existing is not None:
            user = existing
            om = (
                OrganizationMembership.objects.select_for_update()
                .filter(user=user, organization=invitation.organization)
                .first()
            )
            if om is not None and om.is_active:
                raise BadStateError("already_member")
            if om is not None:
                om.is_active = True
                om.role = invitation.role
                om.save(update_fields=["is_active", "role", "updated_at"])
            else:
                OrganizationMembership.objects.create(
                    user=user,
                    organization=invitation.organization,
                    role=invitation.role,
                    is_active=True,
                    created_by=invitation.created_by,
                )
            _sync_location_memberships(user=user, invitation=invitation)
        else:
            if not password:
                raise ValueError("password_required")
            try:
                validate_password(password)
            except DjangoValidationError as exc:
                raise WeakPasswordError(list(exc.messages)) from exc
            user = User.objects.create_user(
                email=invitation.email,
                password=password,
                is_active=True,
                preferred_language=invitation.organization.default_language,
            )
            OrganizationMembership.objects.create(
                user=user,
                organization=invitation.organization,
                role=invitation.role,
                is_active=True,
                created_by=invitation.created_by,
            )
            for loc in invite_locations:
                LocationMembership.objects.create(
                    user=user,
                    location=loc,
                    is_active=True,
                    created_by=invitation.created_by,
                )

        invitation.accepted_at = timezone.now()
        invitation.save(update_fields=["accepted_at", "updated_at"])
        return user


def revoke_invitation(invitation: Invitation, *, by: User) -> None:
    if invitation.revoked_at is not None:
        return
    if invitation.accepted_at is not None:
        raise BadStateError("already_accepted")
    with transaction.atomic():
        locked = Invitation.objects.select_for_update().get(pk=invitation.pk)
        if locked.revoked_at is not None:
            return
        if locked.accepted_at is not None:
            raise BadStateError("already_accepted")
        now = timezone.now()
        locked.revoked_at = now
        locked.revoked_by = by
        locked.save(update_fields=["revoked_at", "revoked_by", "updated_at"])
        invitation.revoked_at = now
        invitation.revoked_by = by
        invitation.updated_at = locked.updated_at


def resend_invitation(invitation: Invitation) -> None:
    if invitation.accepted_at is not None:
        raise BadStateError("already_accepted")
    if invitation.revoked_at is not None:
        raise BadStateError("already_revoked")
    with transaction.atomic():
        locked = Invitation.objects.select_for_update().get(pk=invitation.pk)
        if locked.accepted_at is not None:
            raise BadStateError("already_accepted")
        if locked.revoked_at is not None:
            raise BadStateError("already_revoked")
        locked.expires_at = timezone.now() + INVITE_TTL
        locked.save(update_fields=["expires_at", "updated_at"])
        invitation.expires_at = locked.expires_at
        invitation.updated_at = locked.updated_at
        transaction.on_commit(lambda: _send_invitation_email(locked))
