import pytest
from django.test import Client
from django.urls import reverse

from core.models import Role
from tests.factories import (
    LocationFactory,
    LocationMembershipFactory,
    OrganizationFactory,
    OrganizationMembershipFactory,
    UserFactory,
)


@pytest.mark.django_db
def test_anonymous_returns_404() -> None:
    org = OrganizationFactory()
    response = Client().get(f"/o/{org.slug}/")
    assert response.status_code == 404


@pytest.mark.django_db
def test_admin_renders_dashboard_with_settings_links() -> None:
    membership = OrganizationMembershipFactory(role=Role.ADMIN)
    client = Client()
    client.force_login(membership.user)

    response = client.get(f"/o/{membership.organization.slug}/")

    assert response.status_code == 200
    body = response.content.decode()
    slug = membership.organization.slug
    assert f"/o/{slug}/settings/locations/" in body
    assert f"/o/{slug}/settings/members/" in body
    assert f"/o/{slug}/settings/organization/" in body


@pytest.mark.django_db
def test_operator_with_one_active_location_redirects_to_pos() -> None:
    membership = OrganizationMembershipFactory(role=Role.OPERATOR)
    org = membership.organization
    location = LocationFactory(organization=org, slug="loc-a")
    LocationMembershipFactory(user=membership.user, location=location)

    client = Client()
    client.force_login(membership.user)
    response = client.get(f"/o/{org.slug}/")

    assert response.status_code == 302
    assert response["Location"] == f"/o/{org.slug}/l/loc-a/pos/"


@pytest.mark.django_db
def test_operator_with_multiple_locations_redirects_to_org_pos() -> None:
    membership = OrganizationMembershipFactory(role=Role.OPERATOR)
    org = membership.organization
    LocationMembershipFactory(
        user=membership.user, location=LocationFactory(organization=org)
    )
    LocationMembershipFactory(
        user=membership.user, location=LocationFactory(organization=org)
    )

    client = Client()
    client.force_login(membership.user)
    response = client.get(f"/o/{org.slug}/")

    assert response.status_code == 302
    assert response["Location"] == f"/o/{org.slug}/pos/"


@pytest.mark.django_db
def test_operator_with_zero_locations_redirects_to_org_pos() -> None:
    membership = OrganizationMembershipFactory(role=Role.OPERATOR)
    org = membership.organization

    client = Client()
    client.force_login(membership.user)
    response = client.get(f"/o/{org.slug}/")

    assert response.status_code == 302
    assert response["Location"] == f"/o/{org.slug}/pos/"


@pytest.mark.django_db
def test_operator_inactive_location_excluded_from_single_branch() -> None:
    membership = OrganizationMembershipFactory(role=Role.OPERATOR)
    org = membership.organization
    active = LocationFactory(organization=org, slug="active-loc")
    inactive = LocationFactory(
        organization=org, slug="inactive-loc", is_active=False
    )
    LocationMembershipFactory(user=membership.user, location=active)
    LocationMembershipFactory(user=membership.user, location=inactive)

    client = Client()
    client.force_login(membership.user)
    response = client.get(f"/o/{org.slug}/")

    assert response.status_code == 302
    assert response["Location"] == f"/o/{org.slug}/l/active-loc/pos/"


@pytest.mark.django_db
def test_cross_org_returns_404() -> None:
    membership = OrganizationMembershipFactory(role=Role.ADMIN)
    other_org = OrganizationFactory()

    client = Client()
    client.force_login(membership.user)
    response = client.get(f"/o/{other_org.slug}/")

    assert response.status_code == 404


@pytest.mark.django_db
def test_superuser_renders_admin_dashboard() -> None:
    superuser = UserFactory(superuser=True)
    org = OrganizationFactory()

    client = Client()
    client.force_login(superuser)
    response = client.get(f"/o/{org.slug}/")

    assert response.status_code == 200
    body = response.content.decode()
    assert f"/o/{org.slug}/settings/locations/" in body


@pytest.mark.django_db
def test_dashboard_url_reverses() -> None:
    org = OrganizationFactory()
    assert reverse("core:org_dashboard", args=[org.slug]) == f"/o/{org.slug}/"
