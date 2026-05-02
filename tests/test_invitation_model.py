import uuid
from datetime import timedelta

import pytest
from django.db import IntegrityError
from django.db.models import ProtectedError
from django.utils import timezone

from core.models import Invitation, Role
from tests.factories import (
    LocationFactory,
    OrganizationFactory,
    UserFactory,
)


def _expires() -> timezone.datetime:
    return timezone.now() + timedelta(days=7)


@pytest.mark.django_db
def test_invitation_defaults() -> None:
    org = OrganizationFactory()
    inviter = UserFactory()
    inv = Invitation.objects.create(
        organization=org,
        email="invitee@example.be",
        role=Role.ADMIN,
        created_by=inviter,
        expires_at=_expires(),
    )
    assert isinstance(inv.public_id, uuid.UUID)
    assert inv.public_id.version == 7
    assert inv.accepted_at is None
    assert inv.revoked_at is None
    assert inv.revoked_by is None
    assert inv.created_at is not None
    assert inv.updated_at is not None


@pytest.mark.django_db
def test_email_lowercased_on_save() -> None:
    org = OrganizationFactory()
    inv = Invitation.objects.create(
        organization=org,
        email="MixedCase@Example.BE",
        role=Role.ADMIN,
        created_by=UserFactory(),
        expires_at=_expires(),
    )
    inv.refresh_from_db()
    assert inv.email == "mixedcase@example.be"


@pytest.mark.django_db
def test_two_pending_for_same_org_email_raise_integrity_error() -> None:
    org = OrganizationFactory()
    inviter = UserFactory()
    Invitation.objects.create(
        organization=org,
        email="dup@example.be",
        role=Role.ADMIN,
        created_by=inviter,
        expires_at=_expires(),
    )
    with pytest.raises(IntegrityError):
        Invitation.objects.create(
            organization=org,
            email="dup@example.be",
            role=Role.OPERATOR,
            created_by=inviter,
            expires_at=_expires(),
        )


@pytest.mark.django_db
def test_new_pending_allowed_after_accept() -> None:
    org = OrganizationFactory()
    inviter = UserFactory()
    first = Invitation.objects.create(
        organization=org,
        email="user@example.be",
        role=Role.ADMIN,
        created_by=inviter,
        expires_at=_expires(),
    )
    first.accepted_at = timezone.now()
    first.save(update_fields=["accepted_at", "updated_at"])
    Invitation.objects.create(
        organization=org,
        email="user@example.be",
        role=Role.OPERATOR,
        created_by=inviter,
        expires_at=_expires(),
    )
    assert (
        Invitation.objects.filter(
            organization=org, email="user@example.be"
        ).count()
        == 2
    )


@pytest.mark.django_db
def test_new_pending_allowed_after_revoke() -> None:
    org = OrganizationFactory()
    inviter = UserFactory()
    first = Invitation.objects.create(
        organization=org,
        email="user@example.be",
        role=Role.ADMIN,
        created_by=inviter,
        expires_at=_expires(),
    )
    first.revoked_at = timezone.now()
    first.revoked_by = inviter
    first.save(update_fields=["revoked_at", "revoked_by", "updated_at"])
    Invitation.objects.create(
        organization=org,
        email="user@example.be",
        role=Role.ADMIN,
        created_by=inviter,
        expires_at=_expires(),
    )
    assert (
        Invitation.objects.filter(
            organization=org, email="user@example.be"
        ).count()
        == 2
    )


@pytest.mark.django_db
def test_pending_unique_constraint_scoped_per_org() -> None:
    org_a = OrganizationFactory()
    org_b = OrganizationFactory()
    inviter = UserFactory()
    Invitation.objects.create(
        organization=org_a,
        email="user@example.be",
        role=Role.ADMIN,
        created_by=inviter,
        expires_at=_expires(),
    )
    Invitation.objects.create(
        organization=org_b,
        email="user@example.be",
        role=Role.ADMIN,
        created_by=inviter,
        expires_at=_expires(),
    )
    assert Invitation.objects.filter(email="user@example.be").count() == 2


@pytest.mark.django_db
def test_organization_delete_cascades_invitations() -> None:
    org = OrganizationFactory()
    inviter = UserFactory()
    Invitation.objects.create(
        organization=org,
        email="user@example.be",
        role=Role.ADMIN,
        created_by=inviter,
        expires_at=_expires(),
    )
    org_pk = org.pk
    org.delete()
    assert not Invitation.objects.filter(organization_id=org_pk).exists()


@pytest.mark.django_db
def test_created_by_user_delete_protected() -> None:
    inviter = UserFactory()
    Invitation.objects.create(
        organization=OrganizationFactory(),
        email="user@example.be",
        role=Role.ADMIN,
        created_by=inviter,
        expires_at=_expires(),
    )
    with pytest.raises(ProtectedError):
        inviter.delete()


@pytest.mark.django_db
def test_revoked_by_user_delete_protected() -> None:
    inviter = UserFactory()
    revoker = UserFactory()
    inv = Invitation.objects.create(
        organization=OrganizationFactory(),
        email="user@example.be",
        role=Role.ADMIN,
        created_by=inviter,
        expires_at=_expires(),
    )
    inv.revoked_at = timezone.now()
    inv.revoked_by = revoker
    inv.save(update_fields=["revoked_at", "revoked_by", "updated_at"])
    with pytest.raises(ProtectedError):
        revoker.delete()


@pytest.mark.django_db
def test_locations_m2m_round_trip() -> None:
    org = OrganizationFactory()
    loc1 = LocationFactory(organization=org)
    loc2 = LocationFactory(organization=org)
    inv = Invitation.objects.create(
        organization=org,
        email="op@example.be",
        role=Role.OPERATOR,
        created_by=UserFactory(),
        expires_at=_expires(),
    )
    inv.locations.set([loc1, loc2])
    assert set(inv.locations.values_list("pk", flat=True)) == {loc1.pk, loc2.pk}
    assert set(loc1.invitations.values_list("pk", flat=True)) == {inv.pk}


@pytest.mark.django_db
def test_tenant_objects_filters_by_request_org() -> None:
    org_a = OrganizationFactory()
    org_b = OrganizationFactory()
    inviter = UserFactory()
    Invitation.objects.create(
        organization=org_a,
        email="a@example.be",
        role=Role.ADMIN,
        created_by=inviter,
        expires_at=_expires(),
    )
    Invitation.objects.create(
        organization=org_b,
        email="b@example.be",
        role=Role.ADMIN,
        created_by=inviter,
        expires_at=_expires(),
    )
    qs_a = Invitation.tenant_objects.for_organization(org_a)
    assert {i.email for i in qs_a} == {"a@example.be"}
