from datetime import timedelta
from typing import Any
from unittest.mock import patch

import pytest
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
from core.services.invitation import (
    INVITE_TTL,
    accept_invitation,
    create_invitation,
    resend_invitation,
    revoke_invitation,
)
from core.services.tokens import make_invite_token
from tests.factories import (
    LocationFactory,
    LocationMembershipFactory,
    OrganizationFactory,
    OrganizationMembershipFactory,
    UserFactory,
)

_Capture = Any
_STRONG_PASSWORD = "Hunter2-Strongish!"


# ---- create_invitation ------------------------------------------------------


@pytest.mark.django_db
def test_create_invitation_admin_happy_path() -> None:
    org = OrganizationFactory()
    inviter = UserFactory()
    inv = create_invitation(
        organization=org,
        email="new@example.be",
        role=Role.ADMIN,
        locations=[],
        created_by=inviter,
    )
    assert inv.pk is not None
    assert inv.email == "new@example.be"
    assert inv.role == Role.ADMIN
    assert inv.created_by == inviter
    assert inv.accepted_at is None
    assert inv.revoked_at is None
    delta = inv.expires_at - timezone.now()
    assert timedelta(days=6, hours=23) < delta <= INVITE_TTL


@pytest.mark.django_db
def test_create_invitation_lowercases_email() -> None:
    inv = create_invitation(
        organization=OrganizationFactory(),
        email="MixedCase@Example.BE",
        role=Role.ADMIN,
        locations=[],
        created_by=UserFactory(),
    )
    assert inv.email == "mixedcase@example.be"


@pytest.mark.django_db
def test_create_invitation_rejects_active_member() -> None:
    org = OrganizationFactory()
    member = UserFactory(email="member@example.be")
    OrganizationMembershipFactory(user=member, organization=org)
    with pytest.raises(AlreadyMemberError):
        create_invitation(
            organization=org,
            email="MEMBER@example.be",
            role=Role.ADMIN,
            locations=[],
            created_by=UserFactory(),
        )


@pytest.mark.django_db
def test_create_invitation_allows_re_invite_of_deactivated_member() -> None:
    org = OrganizationFactory()
    user = UserFactory(email="ex@example.be")
    OrganizationMembershipFactory(user=user, organization=org, is_active=False)
    inv = create_invitation(
        organization=org,
        email="ex@example.be",
        role=Role.ADMIN,
        locations=[],
        created_by=UserFactory(),
    )
    assert inv.pk is not None


@pytest.mark.django_db
def test_create_invitation_operator_requires_locations() -> None:
    with pytest.raises(OperatorRequiresLocationsError):
        create_invitation(
            organization=OrganizationFactory(),
            email="op@example.be",
            role=Role.OPERATOR,
            locations=[],
            created_by=UserFactory(),
        )


@pytest.mark.django_db
def test_create_invitation_rejects_cross_org_locations() -> None:
    org_a = OrganizationFactory()
    org_b = OrganizationFactory()
    other_loc = LocationFactory(organization=org_b)
    with pytest.raises(OperatorRequiresLocationsError):
        create_invitation(
            organization=org_a,
            email="op@example.be",
            role=Role.OPERATOR,
            locations=[other_loc],
            created_by=UserFactory(),
        )


@pytest.mark.django_db
def test_create_invitation_rejects_inactive_locations() -> None:
    org = OrganizationFactory()
    loc = LocationFactory(organization=org, is_active=False)
    with pytest.raises(OperatorRequiresLocationsError):
        create_invitation(
            organization=org,
            email="op@example.be",
            role=Role.OPERATOR,
            locations=[loc],
            created_by=UserFactory(),
        )


@pytest.mark.django_db
def test_create_invitation_pending_exists_raises_bad_state() -> None:
    org = OrganizationFactory()
    inviter = UserFactory()
    create_invitation(
        organization=org,
        email="dup@example.be",
        role=Role.ADMIN,
        locations=[],
        created_by=inviter,
    )
    with pytest.raises(BadStateError) as exc:
        create_invitation(
            organization=org,
            email="dup@example.be",
            role=Role.OPERATOR,
            locations=[LocationFactory(organization=org)],
            created_by=inviter,
        )
    assert exc.value.reason == "pending_exists"


@pytest.mark.django_db
def test_create_invitation_fires_email_on_commit(
    django_capture_on_commit_callbacks: _Capture,
) -> None:
    with patch("core.services.invitation.send_templated") as send:
        with django_capture_on_commit_callbacks(execute=True):
            inv = create_invitation(
                organization=OrganizationFactory(default_language="nl-BE"),
                email="invitee@example.be",
                role=Role.ADMIN,
                locations=[],
                created_by=UserFactory(),
            )
        send.assert_called_once()
        args, kwargs = send.call_args
        assert args == ("email/invitation",)
        assert kwargs["language"] == "nl-BE"
        assert kwargs["context"]["org_name"] == inv.organization.name
        assert kwargs["context"]["accept_url"].startswith("http")


@pytest.mark.django_db
def test_create_invitation_email_failure_is_logged_and_swallowed(
    django_capture_on_commit_callbacks: _Capture,
    caplog: pytest.LogCaptureFixture,
) -> None:
    with (
        patch(
            "core.services.invitation.send_templated",
            side_effect=RuntimeError("smtp down"),
        ),
        django_capture_on_commit_callbacks(execute=True),
    ):
        inv = create_invitation(
            organization=OrganizationFactory(),
            email="x@example.be",
            role=Role.ADMIN,
            locations=[],
            created_by=UserFactory(),
        )
    assert inv.pk is not None
    assert any(
        "invitation email send failed" in r.message for r in caplog.records
    )


# ---- accept_invitation -----------------------------------------------------


def _pending_invitation(
    *,
    organization: Organization | None = None,
    email: str = "invitee@example.be",
    role: str = Role.ADMIN,
    locations: list[Location] | None = None,
) -> Invitation:
    org = organization or OrganizationFactory()
    inv = Invitation.objects.create(
        organization=org,
        email=email,
        role=role,
        created_by=UserFactory(),
        expires_at=timezone.now() + INVITE_TTL,
    )
    if locations:
        inv.locations.set(locations)
    return inv


@pytest.mark.django_db
def test_accept_invitation_new_user_creates_user_om_lm() -> None:
    org = OrganizationFactory()
    loc1 = LocationFactory(organization=org)
    loc2 = LocationFactory(organization=org)
    inv = _pending_invitation(
        organization=org,
        email="op@example.be",
        role=Role.OPERATOR,
        locations=[loc1, loc2],
    )
    token = make_invite_token(inv)
    user = accept_invitation(token, password=_STRONG_PASSWORD)
    assert user.email == "op@example.be"
    assert user.is_active is True
    assert user.check_password(_STRONG_PASSWORD)
    assert OrganizationMembership.objects.filter(
        user=user, organization=org, role=Role.OPERATOR, is_active=True
    ).exists()
    assert set(
        LocationMembership.objects.filter(user=user).values_list(
            "location_id", flat=True
        )
    ) == {loc1.pk, loc2.pk}
    inv.refresh_from_db()
    assert inv.accepted_at is not None


@pytest.mark.django_db
def test_accept_invitation_new_user_inherits_org_default_language() -> None:
    org = OrganizationFactory(default_language="fr-BE")
    inv = _pending_invitation(organization=org, email="fr@example.be")
    user = accept_invitation(make_invite_token(inv), password=_STRONG_PASSWORD)
    assert user.preferred_language == "fr-BE"


@pytest.mark.django_db
def test_accept_invitation_new_user_missing_password_raises() -> None:
    inv = _pending_invitation()
    with pytest.raises(ValueError):
        accept_invitation(make_invite_token(inv))
    inv.refresh_from_db()
    assert inv.accepted_at is None
    assert User.objects.filter(email=inv.email).count() == 0


@pytest.mark.django_db
def test_accept_invitation_new_user_weak_password_rolls_back() -> None:
    inv = _pending_invitation()
    with pytest.raises(WeakPasswordError):
        accept_invitation(make_invite_token(inv), password="123")
    inv.refresh_from_db()
    assert inv.accepted_at is None
    assert User.objects.filter(email=inv.email).count() == 0


@pytest.mark.django_db
def test_accept_invitation_existing_user_creates_om_ignores_password() -> None:
    org = OrganizationFactory()
    user = UserFactory(email="known@example.be")
    original_hash = user.password
    inv = _pending_invitation(
        organization=org, email="known@example.be", role=Role.ADMIN
    )
    returned = accept_invitation(make_invite_token(inv), password="ignored")
    user.refresh_from_db()
    assert returned == user
    assert user.password == original_hash
    assert OrganizationMembership.objects.filter(
        user=user, organization=org, role=Role.ADMIN, is_active=True
    ).exists()


@pytest.mark.django_db
def test_accept_invitation_existing_active_member_raises() -> None:
    org = OrganizationFactory()
    user = UserFactory(email="member@example.be")
    OrganizationMembershipFactory(user=user, organization=org)
    inv = Invitation.objects.create(
        organization=org,
        email="member@example.be",
        role=Role.ADMIN,
        created_by=UserFactory(),
        expires_at=timezone.now() + INVITE_TTL,
    )
    with pytest.raises(BadStateError) as exc:
        accept_invitation(make_invite_token(inv))
    assert exc.value.reason == "already_member"


@pytest.mark.django_db
def test_accept_invitation_reactivates_deactivated_membership() -> None:
    org = OrganizationFactory()
    user = UserFactory(email="returning@example.be")
    om = OrganizationMembershipFactory(
        user=user, organization=org, role=Role.OPERATOR, is_active=False
    )
    keep_loc = LocationFactory(organization=org)
    LocationMembershipFactory(user=user, location=keep_loc, is_active=True)

    new_loc = LocationFactory(organization=org)
    inv = _pending_invitation(
        organization=org,
        email="returning@example.be",
        role=Role.ADMIN,
        locations=[new_loc],
    )
    accept_invitation(make_invite_token(inv))

    om.refresh_from_db()
    assert om.is_active is True
    assert om.role == Role.ADMIN
    lm_pairs = LocationMembership.objects.filter(user=user).values_list(
        "location_id", "is_active"
    )
    location_states = {loc_pk: active for loc_pk, active in lm_pairs}
    assert keep_loc.pk in location_states
    assert location_states.get(new_loc.pk) is True


@pytest.mark.django_db
def test_accept_invitation_invalid_token() -> None:
    with pytest.raises(BadStateError) as exc:
        accept_invitation("not-a-token", password=_STRONG_PASSWORD)
    assert exc.value.reason == "invalid_token"


@pytest.mark.django_db
def test_accept_invitation_expired_invitation() -> None:
    inv = _pending_invitation()
    inv.expires_at = timezone.now() - timedelta(hours=1)
    inv.save(update_fields=["expires_at", "updated_at"])
    with pytest.raises(BadStateError) as exc:
        accept_invitation(make_invite_token(inv), password=_STRONG_PASSWORD)
    assert exc.value.reason == "expired"


@pytest.mark.django_db
def test_accept_invitation_already_accepted() -> None:
    inv = _pending_invitation()
    inv.accepted_at = timezone.now()
    inv.save(update_fields=["accepted_at", "updated_at"])
    with pytest.raises(BadStateError) as exc:
        accept_invitation(make_invite_token(inv), password=_STRONG_PASSWORD)
    assert exc.value.reason == "already_accepted"


@pytest.mark.django_db
def test_accept_invitation_already_revoked() -> None:
    inv = _pending_invitation()
    inv.revoked_at = timezone.now()
    inv.revoked_by = UserFactory()
    inv.save(update_fields=["revoked_at", "revoked_by", "updated_at"])
    with pytest.raises(BadStateError) as exc:
        accept_invitation(make_invite_token(inv), password=_STRONG_PASSWORD)
    assert exc.value.reason == "already_revoked"


@pytest.mark.django_db
def test_accept_invitation_stale_locations_does_not_mutate() -> None:
    org = OrganizationFactory()
    loc = LocationFactory(organization=org, is_active=True)
    inv = _pending_invitation(
        organization=org,
        email="op@example.be",
        role=Role.OPERATOR,
        locations=[loc],
    )
    loc.is_active = False
    loc.save(update_fields=["is_active", "updated_at"])
    with pytest.raises(BadStateError) as exc:
        accept_invitation(make_invite_token(inv), password=_STRONG_PASSWORD)
    assert exc.value.reason == "stale_locations"
    inv.refresh_from_db()
    assert inv.accepted_at is None
    assert User.objects.filter(email="op@example.be").count() == 0


@pytest.mark.django_db
def test_accept_invitation_rolls_back_on_lm_failure() -> None:
    org = OrganizationFactory()
    loc = LocationFactory(organization=org)
    inv = _pending_invitation(
        organization=org,
        email="op@example.be",
        role=Role.OPERATOR,
        locations=[loc],
    )
    with (
        patch(
            "core.services.invitation.LocationMembership.objects.create",
            side_effect=RuntimeError("boom"),
        ),
        pytest.raises(RuntimeError),
    ):
        accept_invitation(make_invite_token(inv), password=_STRONG_PASSWORD)
    inv.refresh_from_db()
    assert inv.accepted_at is None
    assert User.objects.filter(email="op@example.be").count() == 0
    assert (
        OrganizationMembership.objects.filter(
            organization=org, user__email="op@example.be"
        ).count()
        == 0
    )


# ---- revoke_invitation -----------------------------------------------------


@pytest.mark.django_db
def test_revoke_invitation_sets_fields() -> None:
    inv = _pending_invitation()
    revoker = UserFactory()
    revoke_invitation(inv, by=revoker)
    inv.refresh_from_db()
    assert inv.revoked_at is not None
    assert inv.revoked_by == revoker


@pytest.mark.django_db
def test_revoke_invitation_idempotent_on_already_revoked() -> None:
    inv = _pending_invitation()
    first_revoker = UserFactory()
    revoke_invitation(inv, by=first_revoker)
    inv.refresh_from_db()
    first_revoked_at = inv.revoked_at
    revoke_invitation(inv, by=UserFactory())
    inv.refresh_from_db()
    assert inv.revoked_at == first_revoked_at
    assert inv.revoked_by == first_revoker


@pytest.mark.django_db
def test_revoke_invitation_raises_on_accepted() -> None:
    inv = _pending_invitation()
    inv.accepted_at = timezone.now()
    inv.save(update_fields=["accepted_at", "updated_at"])
    with pytest.raises(BadStateError) as exc:
        revoke_invitation(inv, by=UserFactory())
    assert exc.value.reason == "already_accepted"


# ---- resend_invitation -----------------------------------------------------


@pytest.mark.django_db
def test_resend_invitation_bumps_expires_at_and_fires_email(
    django_capture_on_commit_callbacks: _Capture,
) -> None:
    inv = _pending_invitation()
    inv.expires_at = timezone.now() + timedelta(days=1)
    inv.save(update_fields=["expires_at", "updated_at"])
    before = inv.expires_at
    with patch("core.services.invitation.send_templated") as send:
        with django_capture_on_commit_callbacks(execute=True):
            resend_invitation(inv)
        send.assert_called_once()
    inv.refresh_from_db()
    delta = inv.expires_at - before
    assert delta > timedelta(days=5)


@pytest.mark.django_db
def test_resend_invitation_raises_on_accepted() -> None:
    inv = _pending_invitation()
    inv.accepted_at = timezone.now()
    inv.save(update_fields=["accepted_at", "updated_at"])
    with pytest.raises(BadStateError) as exc:
        resend_invitation(inv)
    assert exc.value.reason == "already_accepted"


@pytest.mark.django_db
def test_resend_invitation_raises_on_revoked() -> None:
    inv = _pending_invitation()
    inv.revoked_at = timezone.now()
    inv.revoked_by = UserFactory()
    inv.save(update_fields=["revoked_at", "revoked_by", "updated_at"])
    with pytest.raises(BadStateError) as exc:
        resend_invitation(inv)
    assert exc.value.reason == "already_revoked"
