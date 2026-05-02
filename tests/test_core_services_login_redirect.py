import pytest

from core.models import Role
from core.services.login_redirect import login_redirect_for
from tests.factories import (
    OrganizationFactory,
    OrganizationMembershipFactory,
    UserFactory,
)


@pytest.mark.django_db
def test_single_active_membership_returns_org_url() -> None:
    user = UserFactory()
    org = OrganizationFactory(slug="acme")
    OrganizationMembershipFactory(user=user, organization=org, role=Role.ADMIN)
    assert login_redirect_for(user) == "/o/acme/"


@pytest.mark.django_db
def test_multiple_active_memberships_returns_picker() -> None:
    user = UserFactory()
    OrganizationMembershipFactory(user=user, role=Role.ADMIN)
    OrganizationMembershipFactory(user=user, role=Role.ADMIN)
    assert login_redirect_for(user) == "/orgs/"


@pytest.mark.django_db
def test_no_membership_returns_picker() -> None:
    user = UserFactory()
    assert login_redirect_for(user) == "/orgs/"


@pytest.mark.django_db
def test_inactive_membership_excluded() -> None:
    user = UserFactory()
    inactive_org = OrganizationFactory(slug="inactive")
    OrganizationMembershipFactory(
        user=user,
        organization=inactive_org,
        role=Role.ADMIN,
        is_active=False,
    )
    active_org = OrganizationFactory(slug="active")
    OrganizationMembershipFactory(
        user=user,
        organization=active_org,
        role=Role.ADMIN,
        is_active=True,
    )
    assert login_redirect_for(user) == "/o/active/"
