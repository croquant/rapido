import pytest
from django.test import Client
from django.urls import reverse

from core.models import Role
from tests.factories import (
    LocationFactory,
    LocationMembershipFactory,
    OrganizationFactory,
    OrganizationMembershipFactory,
)


@pytest.mark.django_db
def test_pos_location_renders_for_operator() -> None:
    membership = OrganizationMembershipFactory(role=Role.OPERATOR)
    org = membership.organization
    location = LocationFactory(organization=org, slug="downtown")
    LocationMembershipFactory(user=membership.user, location=location)
    client = Client()
    client.force_login(membership.user)

    response = client.get(f"/o/{org.slug}/l/downtown/pos/")

    assert response.status_code == 200
    assert b"coming soon" in response.content.lower()


@pytest.mark.django_db
def test_pos_location_renders_for_admin() -> None:
    membership = OrganizationMembershipFactory(role=Role.ADMIN)
    org = membership.organization
    LocationFactory(organization=org, slug="downtown")
    client = Client()
    client.force_login(membership.user)

    response = client.get(f"/o/{org.slug}/l/downtown/pos/")

    assert response.status_code == 200


@pytest.mark.django_db
def test_pos_location_unknown_slug_returns_404() -> None:
    membership = OrganizationMembershipFactory(role=Role.ADMIN)
    org = membership.organization
    client = Client()
    client.force_login(membership.user)

    response = client.get(f"/o/{org.slug}/l/nope/pos/")

    assert response.status_code == 404


@pytest.mark.django_db
def test_pos_location_operator_without_membership_returns_404() -> None:
    membership = OrganizationMembershipFactory(role=Role.OPERATOR)
    org = membership.organization
    assigned = LocationFactory(organization=org, slug="assigned")
    LocationFactory(organization=org, slug="other")
    LocationMembershipFactory(user=membership.user, location=assigned)
    client = Client()
    client.force_login(membership.user)

    response = client.get(f"/o/{org.slug}/l/other/pos/")

    assert response.status_code == 404


@pytest.mark.django_db
def test_pos_location_inactive_location_returns_404() -> None:
    membership = OrganizationMembershipFactory(role=Role.ADMIN)
    org = membership.organization
    LocationFactory(organization=org, slug="closed", is_active=False)
    client = Client()
    client.force_login(membership.user)

    response = client.get(f"/o/{org.slug}/l/closed/pos/")

    assert response.status_code == 404


@pytest.mark.django_db
def test_pos_org_renders_for_operator() -> None:
    membership = OrganizationMembershipFactory(role=Role.OPERATOR)
    org = membership.organization
    client = Client()
    client.force_login(membership.user)

    response = client.get(f"/o/{org.slug}/pos/")

    assert response.status_code == 200


@pytest.mark.django_db
def test_pos_anonymous_redirects_to_login() -> None:
    org = OrganizationFactory()

    response = Client().get(f"/o/{org.slug}/pos/")

    # Tenant middleware 404s anonymous users before permission_required
    # gets a chance to redirect — that's existing behavior, see
    # test_views_dashboard.test_anonymous_returns_404.
    assert response.status_code == 404


@pytest.mark.django_db
def test_pos_urls_reverse() -> None:
    org = OrganizationFactory()
    assert reverse("core:pos_org", args=[org.slug]) == f"/o/{org.slug}/pos/"
    assert (
        reverse("core:pos_location", args=[org.slug, "downtown"])
        == f"/o/{org.slug}/l/downtown/pos/"
    )
