import pytest
from django.test import Client

from core.models import (
    LocationMembership,
    Organization,
    OrganizationMembership,
    Role,
)
from tests.factories import (
    InvitationFactory,
    LocationFactory,
    OrganizationFactory,
    OrganizationMembershipFactory,
    UserFactory,
)


def _admin_client(
    org: Organization | None = None,
) -> tuple[Client, OrganizationMembership]:
    membership = OrganizationMembershipFactory(
        role=Role.ADMIN,
        organization=org or OrganizationFactory(),
    )
    client = Client()
    client.force_login(membership.user)
    return client, membership


def _routes(slug: str, pk: int = 1, lpk: int = 1) -> dict[str, str]:
    base = f"/o/{slug}/settings/members"
    return {
        "list": f"{base}/",
        "detail": f"{base}/{pk}/",
        "role": f"{base}/{pk}/role/",
        "deactivate": f"{base}/{pk}/deactivate/",
        "reactivate": f"{base}/{pk}/reactivate/",
        "toggle_location": f"{base}/{pk}/locations/{lpk}/toggle/",
    }


# ---- anonymous --------------------------------------------------------------


@pytest.mark.django_db
def test_anonymous_list_returns_404() -> None:
    org = OrganizationFactory()
    response = Client().get(_routes(org.slug)["list"])
    assert response.status_code == 404


# ---- operator forbidden -----------------------------------------------------


@pytest.mark.django_db
def test_operator_forbidden_on_all_routes() -> None:
    op = OrganizationMembershipFactory(role=Role.OPERATOR)
    client = Client()
    client.force_login(op.user)
    routes = _routes(op.organization.slug, op.pk, 1)

    assert client.get(routes["list"]).status_code == 403
    assert client.get(routes["detail"]).status_code == 403
    assert client.post(routes["role"], {"role": "OPERATOR"}).status_code == 403
    assert client.post(routes["deactivate"]).status_code == 403
    assert client.post(routes["reactivate"]).status_code == 403
    assert client.post(routes["toggle_location"]).status_code == 403


# ---- list -------------------------------------------------------------------


@pytest.mark.django_db
def test_admin_list_shows_members_pending_and_archive() -> None:
    client, admin = _admin_client()
    org = admin.organization
    operator = OrganizationMembershipFactory(
        role=Role.OPERATOR, organization=org
    )
    InvitationFactory(
        organization=org, email="pending@example.be", created_by=admin.user
    )
    revoked_inv = InvitationFactory(
        organization=org, email="revoked@example.be", created_by=admin.user
    )
    from django.utils import timezone

    revoked_inv.revoked_at = timezone.now()
    revoked_inv.save(update_fields=["revoked_at"])

    response = client.get(_routes(org.slug)["list"])

    assert response.status_code == 200
    body = response.content.decode()
    assert admin.user.email in body
    assert operator.user.email in body
    assert "pending@example.be" in body
    assert "revoked@example.be" in body


@pytest.mark.django_db
def test_list_disables_role_and_deactivate_for_only_active_admin() -> None:
    client, admin = _admin_client()
    OrganizationMembershipFactory(
        role=Role.OPERATOR, organization=admin.organization
    )

    response = client.get(_routes(admin.organization.slug)["list"])

    assert response.status_code == 200
    body = response.content.decode()
    row_marker = f'id="member-row-{admin.pk}"'
    assert row_marker in body
    admin_row = body.split(row_marker, 1)[1].split("</tr>", 1)[0]
    assert "disabled" in admin_row
    assert admin_row.count("disabled") >= 2  # role <select> + deactivate button


@pytest.mark.django_db
def test_list_enables_controls_when_co_admin_exists() -> None:
    client, admin = _admin_client()
    OrganizationMembershipFactory(
        role=Role.ADMIN, organization=admin.organization
    )

    response = client.get(_routes(admin.organization.slug)["list"])

    assert response.status_code == 200
    body = response.content.decode()
    row_marker = f'id="member-row-{admin.pk}"'
    admin_row = body.split(row_marker, 1)[1].split("</tr>", 1)[0]
    assert "disabled" not in admin_row


@pytest.mark.django_db
def test_admin_list_does_not_leak_other_orgs() -> None:
    client, admin = _admin_client()
    other_org = OrganizationFactory()
    OrganizationMembershipFactory(role=Role.ADMIN, organization=other_org)
    InvitationFactory(organization=other_org, email="otherorg@example.be")

    response = client.get(_routes(admin.organization.slug)["list"])

    assert response.status_code == 200
    assert "otherorg@example.be" not in response.content.decode()


# ---- change role ------------------------------------------------------------


@pytest.mark.django_db
def test_change_role_demote_admin_when_other_admin_exists() -> None:
    client, admin = _admin_client()
    org = admin.organization
    OrganizationMembershipFactory(role=Role.ADMIN, organization=org)
    target = OrganizationMembershipFactory(role=Role.ADMIN, organization=org)

    response = client.post(
        _routes(org.slug, target.pk)["role"],
        {"role": "OPERATOR"},
        HTTP_HX_REQUEST="true",
    )

    assert response.status_code == 200
    target.refresh_from_db()
    assert target.role == "OPERATOR"
    assert f'id="member-row-{target.pk}"' in response.content.decode()


@pytest.mark.django_db
def test_change_role_last_admin_returns_422_with_reverted_row() -> None:
    client, admin = _admin_client()

    response = client.post(
        _routes(admin.organization.slug, admin.pk)["role"],
        {"role": "OPERATOR"},
        HTTP_HX_REQUEST="true",
    )

    assert response.status_code == 422
    admin.refresh_from_db()
    assert admin.role == "ADMIN"
    body = response.content.decode()
    assert f'id="member-row-{admin.pk}"' in body
    assert response.headers.get("HX-Trigger") == "members:role_change_failed"
    assert 'id="flash"' in body
    assert 'hx-swap-oob="true"' in body
    assert "last active admin" in body


# ---- deactivate / reactivate -----------------------------------------------


@pytest.mark.django_db
def test_deactivate_last_admin_returns_422() -> None:
    client, admin = _admin_client()

    response = client.post(
        _routes(admin.organization.slug, admin.pk)["deactivate"],
        HTTP_HX_REQUEST="true",
    )

    assert response.status_code == 422
    admin.refresh_from_db()
    assert admin.is_active is True
    body = response.content.decode()
    assert 'id="flash"' in body
    assert 'hx-swap-oob="true"' in body
    assert "last active admin" in body


@pytest.mark.django_db
def test_deactivate_then_reactivate_round_trip() -> None:
    client, admin = _admin_client()
    org = admin.organization
    OrganizationMembershipFactory(role=Role.ADMIN, organization=org)
    target = OrganizationMembershipFactory(role=Role.OPERATOR, organization=org)

    deactivate_response = client.post(
        _routes(org.slug, target.pk)["deactivate"],
        HTTP_HX_REQUEST="true",
    )
    assert deactivate_response.status_code == 200
    target.refresh_from_db()
    assert target.is_active is False

    reactivate_response = client.post(
        _routes(org.slug, target.pk)["reactivate"],
        HTTP_HX_REQUEST="true",
    )
    assert reactivate_response.status_code == 200
    target.refresh_from_db()
    assert target.is_active is True


# ---- detail + location toggle ----------------------------------------------


@pytest.mark.django_db
def test_detail_admin_shows_location_chips() -> None:
    client, admin = _admin_client()
    org = admin.organization
    LocationFactory(organization=org, name="Alpha")
    LocationFactory(organization=org, name="Beta")
    operator = OrganizationMembershipFactory(
        role=Role.OPERATOR, organization=org
    )

    response = client.get(_routes(org.slug, operator.pk)["detail"])

    assert response.status_code == 200
    body = response.content.decode()
    assert "Alpha" in body
    assert "Beta" in body


@pytest.mark.django_db
def test_toggle_location_creates_then_deactivates_same_row() -> None:
    client, admin = _admin_client()
    org = admin.organization
    location = LocationFactory(organization=org)
    operator = OrganizationMembershipFactory(
        role=Role.OPERATOR, organization=org
    )

    on = client.post(
        _routes(org.slug, operator.pk, location.pk)["toggle_location"],
        HTTP_HX_REQUEST="true",
    )
    assert on.status_code == 200
    assert (
        LocationMembership.objects.filter(
            user=operator.user, location=location, is_active=True
        ).count()
        == 1
    )

    off = client.post(
        _routes(org.slug, operator.pk, location.pk)["toggle_location"],
        HTTP_HX_REQUEST="true",
    )
    assert off.status_code == 200
    assert (
        LocationMembership.objects.filter(
            user=operator.user, location=location
        ).count()
        == 1
    )
    assert (
        LocationMembership.objects.get(
            user=operator.user, location=location
        ).is_active
        is False
    )

    on_again = client.post(
        _routes(org.slug, operator.pk, location.pk)["toggle_location"],
        HTTP_HX_REQUEST="true",
    )
    assert on_again.status_code == 200
    assert (
        LocationMembership.objects.filter(
            user=operator.user, location=location
        ).count()
        == 1
    )


@pytest.mark.django_db
def test_toggle_location_inactive_location_404() -> None:
    client, admin = _admin_client()
    org = admin.organization
    inactive = LocationFactory(organization=org, is_active=False)
    operator = OrganizationMembershipFactory(
        role=Role.OPERATOR, organization=org
    )

    response = client.post(
        _routes(org.slug, operator.pk, inactive.pk)["toggle_location"],
        HTTP_HX_REQUEST="true",
    )
    assert response.status_code == 404


# ---- cross-org tenant scoping ----------------------------------------------


@pytest.mark.django_db
def test_cross_org_detail_404() -> None:
    client, admin = _admin_client()
    other_org_member = OrganizationMembershipFactory(
        role=Role.OPERATOR, organization=OrganizationFactory()
    )

    response = client.get(
        _routes(admin.organization.slug, other_org_member.pk)["detail"]
    )
    assert response.status_code == 404


@pytest.mark.django_db
def test_cross_org_role_change_404() -> None:
    client, admin = _admin_client()
    other_org_member = OrganizationMembershipFactory(
        role=Role.OPERATOR, organization=OrganizationFactory()
    )

    response = client.post(
        _routes(admin.organization.slug, other_org_member.pk)["role"],
        {"role": "ADMIN"},
    )
    assert response.status_code == 404


# ---- method guards ----------------------------------------------------------


@pytest.mark.django_db
def test_get_on_action_endpoints_returns_405() -> None:
    client, admin = _admin_client()
    routes = _routes(admin.organization.slug, admin.pk, 1)
    assert client.get(routes["role"]).status_code == 405
    assert client.get(routes["deactivate"]).status_code == 405
    assert client.get(routes["reactivate"]).status_code == 405
    assert client.get(routes["toggle_location"]).status_code == 405


# ---- invalid form ------------------------------------------------------------


@pytest.mark.django_db
def test_change_role_invalid_payload_returns_422() -> None:
    client, admin = _admin_client()
    org = admin.organization
    target = OrganizationMembershipFactory(role=Role.OPERATOR, organization=org)

    response = client.post(
        _routes(org.slug, target.pk)["role"],
        {"role": "WIZARD"},
        HTTP_HX_REQUEST="true",
    )
    assert response.status_code == 422
    target.refresh_from_db()
    assert target.role == "OPERATOR"


# ---- superuser sanity -------------------------------------------------------


@pytest.mark.django_db
def test_superuser_can_access_list() -> None:
    superuser = UserFactory(superuser=True)
    org = OrganizationFactory()
    client = Client()
    client.force_login(superuser)

    response = client.get(_routes(org.slug)["list"])
    assert response.status_code == 200
