import pytest

from core.models import Role
from core.services.login_redirect import login_redirect_for
from tests.factories import (
    LocationFactory,
    LocationMembershipFactory,
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


@pytest.mark.django_db
def test_admin_with_single_location_membership_still_lands_on_org() -> None:
    # Whitepaper §1: only OPERATOR triggers the POS shortcut.
    user = UserFactory()
    org = OrganizationFactory(slug="acme")
    OrganizationMembershipFactory(user=user, organization=org, role=Role.ADMIN)
    LocationMembershipFactory(
        user=user, location=LocationFactory(organization=org)
    )
    assert login_redirect_for(user) == "/o/acme/"


@pytest.mark.django_db
def test_operator_single_location_returns_pos_url() -> None:
    user = UserFactory()
    org = OrganizationFactory(slug="acme")
    OrganizationMembershipFactory(
        user=user, organization=org, role=Role.OPERATOR
    )
    location = LocationFactory(organization=org, slug="downtown")
    LocationMembershipFactory(user=user, location=location)
    assert login_redirect_for(user) == "/o/acme/l/downtown/pos/"


@pytest.mark.django_db
def test_operator_multiple_locations_returns_org_url() -> None:
    user = UserFactory()
    org = OrganizationFactory(slug="acme")
    OrganizationMembershipFactory(
        user=user, organization=org, role=Role.OPERATOR
    )
    LocationMembershipFactory(
        user=user, location=LocationFactory(organization=org)
    )
    LocationMembershipFactory(
        user=user, location=LocationFactory(organization=org)
    )
    assert login_redirect_for(user) == "/o/acme/"


@pytest.mark.django_db
def test_operator_zero_locations_returns_org_url() -> None:
    user = UserFactory()
    org = OrganizationFactory(slug="acme")
    OrganizationMembershipFactory(
        user=user, organization=org, role=Role.OPERATOR
    )
    assert login_redirect_for(user) == "/o/acme/"


@pytest.mark.django_db
def test_operator_inactive_location_membership_ignored() -> None:
    # Inactive LocationMembership doesn't count toward the "exactly one" branch.
    user = UserFactory()
    org = OrganizationFactory(slug="acme")
    OrganizationMembershipFactory(
        user=user, organization=org, role=Role.OPERATOR
    )
    LocationMembershipFactory(
        user=user,
        location=LocationFactory(organization=org),
        is_active=False,
    )
    LocationMembershipFactory(
        user=user, location=LocationFactory(organization=org, slug="active-loc")
    )
    assert login_redirect_for(user) == "/o/acme/l/active-loc/pos/"
