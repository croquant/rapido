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
def test_anonymous_redirects_to_login() -> None:
    client = Client()
    response = client.get(reverse("core:org_picker"))
    assert response.status_code == 302
    assert response["Location"].startswith(reverse("core:login"))
    assert "next=/orgs/" in response["Location"]


@pytest.mark.django_db
def test_zero_memberships_renders_empty_state() -> None:
    user = UserFactory()
    client = Client()
    client.force_login(user)

    response = client.get(reverse("core:org_picker"))

    assert response.status_code == 200
    assert "auth/org_picker.html" in [t.name for t in response.templates]
    assert b"No organisations" in response.content


@pytest.mark.django_db
def test_single_active_admin_redirects_to_org() -> None:
    user = UserFactory()
    org = OrganizationFactory(slug="acme")
    OrganizationMembershipFactory(user=user, organization=org, role=Role.ADMIN)
    client = Client()
    client.force_login(user)

    response = client.get(reverse("core:org_picker"))

    assert response.status_code == 302
    assert response["Location"] == "/o/acme/"


@pytest.mark.django_db
def test_multiple_memberships_lists_orgs() -> None:
    user = UserFactory()
    org_a = OrganizationFactory(name="Acme", slug="acme")
    org_b = OrganizationFactory(name="Beta", slug="beta")
    OrganizationMembershipFactory(
        user=user, organization=org_a, role=Role.ADMIN
    )
    OrganizationMembershipFactory(
        user=user, organization=org_b, role=Role.OPERATOR
    )
    client = Client()
    client.force_login(user)

    response = client.get(reverse("core:org_picker"))

    assert response.status_code == 200
    assert b"Acme" in response.content
    assert b"Beta" in response.content
    assert b'href="/o/acme/"' in response.content
    assert b'href="/o/beta/"' in response.content


@pytest.mark.django_db
def test_inactive_membership_excluded_from_count() -> None:
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
    client = Client()
    client.force_login(user)

    response = client.get(reverse("core:org_picker"))

    assert response.status_code == 302
    assert response["Location"] == "/o/active/"


@pytest.mark.django_db
def test_operator_single_location_redirects_to_pos() -> None:
    # Picker reuses login_redirect_for so the OPERATOR + single-location
    # shortcut from /login/ also fires when the picker is hit directly.
    user = UserFactory()
    org = OrganizationFactory(slug="acme")
    OrganizationMembershipFactory(
        user=user, organization=org, role=Role.OPERATOR
    )
    location = LocationFactory(organization=org, slug="downtown")
    LocationMembershipFactory(user=user, location=location)
    client = Client()
    client.force_login(user)

    response = client.get(reverse("core:org_picker"))

    assert response.status_code == 302
    assert response["Location"] == "/o/acme/l/downtown/pos/"
    assert client.get(response["Location"]).status_code == 200
