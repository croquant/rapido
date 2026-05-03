import pytest
from django.test import Client

from core.models import Location, LocationMembership, Organization, Role
from tests.factories import (
    LocationFactory,
    LocationMembershipFactory,
    OrganizationFactory,
    OrganizationMembershipFactory,
    UserFactory,
)


def _admin_client(
    org: Organization | None = None,
) -> tuple[Client, Organization]:
    membership = OrganizationMembershipFactory(
        role=Role.ADMIN,
        organization=org or OrganizationFactory(),
    )
    client = Client()
    client.force_login(membership.user)
    return client, membership.organization


def _routes(slug: str, pk: int = 1) -> dict[str, str]:
    base = f"/o/{slug}/settings/locations"
    return {
        "list": f"{base}/",
        "create": f"{base}/new/",
        "edit": f"{base}/{pk}/edit/",
        "deactivate": f"{base}/{pk}/deactivate/",
        "reactivate": f"{base}/{pk}/reactivate/",
    }


# ---- anonymous --------------------------------------------------------------


@pytest.mark.django_db
@pytest.mark.parametrize(
    "key", ["list", "create", "edit", "deactivate", "reactivate"]
)
def test_anonymous_redirects_or_404(key: str) -> None:
    org = OrganizationFactory()
    location = LocationFactory(organization=org)
    routes = _routes(org.slug, location.pk)
    method = "post" if key in {"deactivate", "reactivate"} else "get"
    response = getattr(Client(), method)(routes[key])
    # TenantMiddleware raises 404 for unauthenticated access to /o/<slug>/.
    assert response.status_code == 404


# ---- operator forbidden -----------------------------------------------------


@pytest.mark.django_db
def test_operator_forbidden_on_all_routes() -> None:
    membership = OrganizationMembershipFactory(role=Role.OPERATOR)
    org = membership.organization
    location = LocationFactory(organization=org)
    client = Client()
    client.force_login(membership.user)

    routes = _routes(org.slug, location.pk)
    assert client.get(routes["list"]).status_code == 403
    assert client.get(routes["create"]).status_code == 403
    assert client.post(routes["create"], {}).status_code == 403
    assert client.get(routes["edit"]).status_code == 403
    assert client.post(routes["edit"], {}).status_code == 403
    assert client.post(routes["deactivate"]).status_code == 403
    assert client.post(routes["reactivate"]).status_code == 403


# ---- list -------------------------------------------------------------------


@pytest.mark.django_db
def test_admin_list_shows_active_and_inactive() -> None:
    client, org = _admin_client()
    LocationFactory(organization=org, name="Alpha", is_active=True)
    LocationFactory(organization=org, name="Beta", is_active=False)

    response = client.get(_routes(org.slug)["list"])

    assert response.status_code == 200
    body = response.content.decode()
    assert "Alpha" in body
    assert "Beta" in body
    # Active sorts first (order_by -is_active, name).
    assert body.index("Alpha") < body.index("Beta")


@pytest.mark.django_db
def test_admin_list_does_not_leak_other_orgs() -> None:
    client, org = _admin_client()
    other = OrganizationFactory()
    LocationFactory(organization=other, name="OtherOrgLoc")

    response = client.get(_routes(org.slug)["list"])

    assert response.status_code == 200
    assert "OtherOrgLoc" not in response.content.decode()


# ---- create -----------------------------------------------------------------


@pytest.mark.django_db
def test_admin_create_persists_with_request_org() -> None:
    client, org = _admin_client()
    response = client.post(
        _routes(org.slug)["create"],
        {
            "name": "Main",
            "slug": "main",
            "street": "Rue 1",
            "postal_code": "1000",
            "city": "Brussels",
            "phone": "",
        },
    )
    assert response.status_code == 302
    assert response["Location"] == _routes(org.slug)["list"]
    loc = Location.tenant_objects.for_organization(org).get(slug="main")
    assert loc.name == "Main"
    assert loc.is_active is True


@pytest.mark.django_db
def test_admin_create_duplicate_slug_same_org_renders_form_error() -> None:
    client, org = _admin_client()
    LocationFactory(organization=org, slug="dup")

    response = client.post(
        _routes(org.slug)["create"],
        {
            "name": "Dup",
            "slug": "dup",
            "street": "Rue",
            "postal_code": "1000",
            "city": "Brussels",
            "phone": "",
        },
    )
    assert response.status_code == 200
    assert "already exists" in response.content.decode()
    assert (
        Location.tenant_objects.for_organization(org).filter(slug="dup").count()
        == 1
    )


@pytest.mark.django_db
def test_create_same_slug_different_org_succeeds() -> None:
    client, org = _admin_client()
    other = OrganizationFactory()
    LocationFactory(organization=other, slug="shared")

    response = client.post(
        _routes(org.slug)["create"],
        {
            "name": "Shared",
            "slug": "shared",
            "street": "Rue",
            "postal_code": "1000",
            "city": "Brussels",
            "phone": "",
        },
    )
    assert response.status_code == 302
    assert (
        Location.tenant_objects.for_organization(org)
        .filter(slug="shared")
        .exists()
    )


# ---- edit -------------------------------------------------------------------


@pytest.mark.django_db
def test_admin_edit_get_omits_slug_field() -> None:
    client, org = _admin_client()
    location = LocationFactory(organization=org, slug="immutable")

    response = client.get(_routes(org.slug, location.pk)["edit"])

    assert response.status_code == 200
    body = response.content.decode()
    assert 'name="slug"' not in body
    # Slug still shown read-only.
    assert "immutable" in body


@pytest.mark.django_db
def test_admin_edit_post_updates_fields() -> None:
    client, org = _admin_client()
    location = LocationFactory(organization=org, name="Old")

    response = client.post(
        _routes(org.slug, location.pk)["edit"],
        {
            "name": "New",
            "street": "Rue 2",
            "postal_code": "2000",
            "city": "Antwerp",
            "phone": "+3201",
        },
    )
    assert response.status_code == 302
    location.refresh_from_db()
    assert location.name == "New"
    assert location.city == "Antwerp"
    # Slug unchanged because field was dropped from the form.
    assert (
        location.slug
        == LocationFactory._meta.model.objects.get(pk=location.pk).slug
    )


# ---- deactivate / reactivate ------------------------------------------------


@pytest.mark.django_db
def test_admin_deactivate_htmx_returns_row_partial() -> None:
    client, org = _admin_client()
    location = LocationFactory(organization=org, is_active=True)

    response = client.post(
        _routes(org.slug, location.pk)["deactivate"],
        HTTP_HX_REQUEST="true",
    )

    assert response.status_code == 200
    body = response.content.decode()
    assert f'id="location-row-{location.pk}"' in body
    assert "Reactivate" in body
    location.refresh_from_db()
    assert location.is_active is False


@pytest.mark.django_db
def test_deactivate_preserves_location_memberships() -> None:
    client, org = _admin_client()
    location = LocationFactory(organization=org, is_active=True)
    user = UserFactory()
    LocationMembershipFactory(user=user, location=location)

    response = client.post(
        _routes(org.slug, location.pk)["deactivate"],
        HTTP_HX_REQUEST="true",
    )

    assert response.status_code == 200
    assert LocationMembership.objects.filter(
        user=user, location=location
    ).exists()


@pytest.mark.django_db
def test_admin_deactivate_non_htmx_redirects_to_list() -> None:
    client, org = _admin_client()
    location = LocationFactory(organization=org, is_active=True)

    response = client.post(_routes(org.slug, location.pk)["deactivate"])

    assert response.status_code == 302
    assert response["Location"] == _routes(org.slug)["list"]
    location.refresh_from_db()
    assert location.is_active is False


@pytest.mark.django_db
def test_admin_reactivate_htmx_returns_row_partial() -> None:
    client, org = _admin_client()
    location = LocationFactory(organization=org, is_active=False)

    response = client.post(
        _routes(org.slug, location.pk)["reactivate"],
        HTTP_HX_REQUEST="true",
    )

    assert response.status_code == 200
    body = response.content.decode()
    assert f'id="location-row-{location.pk}"' in body
    assert "Deactivate" in body
    location.refresh_from_db()
    assert location.is_active is True


# ---- method guards ----------------------------------------------------------


@pytest.mark.django_db
def test_get_on_deactivate_or_reactivate_returns_405() -> None:
    client, org = _admin_client()
    location = LocationFactory(organization=org)
    routes = _routes(org.slug, location.pk)
    assert client.get(routes["deactivate"]).status_code == 405
    assert client.get(routes["reactivate"]).status_code == 405


# ---- cross-org tenant scoping ----------------------------------------------


@pytest.mark.django_db
def test_cross_org_edit_returns_404() -> None:
    client, org = _admin_client()
    other_org = OrganizationFactory()
    other_loc = LocationFactory(organization=other_org)

    response = client.get(_routes(org.slug, other_loc.pk)["edit"])
    assert response.status_code == 404


@pytest.mark.django_db
def test_cross_org_deactivate_returns_404() -> None:
    client, org = _admin_client()
    other_org = OrganizationFactory()
    other_loc = LocationFactory(organization=other_org, is_active=True)

    response = client.post(_routes(org.slug, other_loc.pk)["deactivate"])
    assert response.status_code == 404
    other_loc.refresh_from_db()
    assert other_loc.is_active is True


@pytest.mark.django_db
def test_cross_org_reactivate_returns_404() -> None:
    client, org = _admin_client()
    other_org = OrganizationFactory()
    other_loc = LocationFactory(organization=other_org, is_active=False)

    response = client.post(_routes(org.slug, other_loc.pk)["reactivate"])
    assert response.status_code == 404
    other_loc.refresh_from_db()
    assert other_loc.is_active is False


# ---- superuser sanity -------------------------------------------------------


@pytest.mark.django_db
def test_superuser_can_access_list() -> None:
    superuser = UserFactory(superuser=True)
    org = OrganizationFactory()
    LocationFactory(organization=org, name="ListedForSuperuser")

    client = Client()
    client.force_login(superuser)
    response = client.get(_routes(org.slug)["list"])

    assert response.status_code == 200
    assert "ListedForSuperuser" in response.content.decode()
