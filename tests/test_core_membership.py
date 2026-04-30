import pytest
from django.db import IntegrityError
from django.db.models import ProtectedError

from core.models import OrganizationMembership, Role
from tests.factories import (
    OrganizationFactory,
    OrganizationMembershipFactory,
    UserFactory,
)


def test_role_choices() -> None:
    assert Role.choices == [
        ("ADMIN", "Admin"),
        ("OPERATOR", "Operator"),
    ]


@pytest.mark.django_db
def test_membership_str_contains_email_and_org() -> None:
    m = OrganizationMembershipFactory()
    s = str(m)
    assert m.user.email in s
    assert m.organization.name in s
    assert "ADMIN" in s


@pytest.mark.django_db
def test_default_is_active_true() -> None:
    m = OrganizationMembershipFactory()
    assert m.is_active is True


@pytest.mark.django_db
def test_membership_inherits_timestamps() -> None:
    m = OrganizationMembershipFactory()
    assert m.created_at is not None
    assert m.updated_at is not None


@pytest.mark.django_db
def test_unique_user_organization() -> None:
    user = UserFactory()
    org = OrganizationFactory()
    OrganizationMembershipFactory(user=user, organization=org)
    with pytest.raises(IntegrityError):
        OrganizationMembershipFactory(user=user, organization=org)


@pytest.mark.django_db
def test_same_user_two_orgs_allowed() -> None:
    user = UserFactory()
    OrganizationMembershipFactory(user=user)
    OrganizationMembershipFactory(user=user)
    assert user.organization_memberships.count() == 2


@pytest.mark.django_db
def test_deleting_user_cascades_membership() -> None:
    m = OrganizationMembershipFactory()
    pk = m.pk
    m.user.delete()
    assert not OrganizationMembership.objects.filter(pk=pk).exists()


@pytest.mark.django_db
def test_deleting_org_with_memberships_blocked() -> None:
    m = OrganizationMembershipFactory()
    with pytest.raises(ProtectedError):
        m.organization.delete()


@pytest.mark.django_db
def test_created_by_nullable() -> None:
    m = OrganizationMembershipFactory(created_by=None)
    assert m.created_by is None


@pytest.mark.django_db
def test_created_by_protect() -> None:
    creator = UserFactory()
    OrganizationMembershipFactory(created_by=creator)
    with pytest.raises(ProtectedError):
        creator.delete()


@pytest.mark.django_db
def test_related_names() -> None:
    m = OrganizationMembershipFactory()
    assert m.user.organization_memberships.filter(pk=m.pk).exists()
    assert m.organization.organization_memberships.filter(
        pk=m.pk
    ).exists()
