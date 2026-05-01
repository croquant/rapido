from typing import Any

import pytest
from django.test import Client
from django.urls import reverse

from core.models import (
    Location,
    LocationMembership,
    Organization,
    OrganizationMembership,
    Role,
    User,
)
from tests.factories import (
    LocationFactory,
    LocationMembershipFactory,
    OrganizationFactory,
    OrganizationMembershipFactory,
    UserFactory,
)

# ---- Smoke ---------------------------------------------------------------


@pytest.mark.django_db
@pytest.mark.parametrize(
    "url_name",
    [
        "admin:core_organization_changelist",
        "admin:core_user_changelist",
        "admin:core_organizationmembership_changelist",
        "admin:core_location_changelist",
        "admin:core_locationmembership_changelist",
    ],
)
def test_admin_changelist_renders(admin_client: Client, url_name: str) -> None:
    response = admin_client.get(reverse(url_name))
    assert response.status_code == 200


# ---- User add form satisfies acceptance criterion -------------------------


@pytest.mark.django_db
def test_user_add_form_exposes_only_email_and_password(
    admin_client: Client,
) -> None:
    response = admin_client.get(reverse("admin:core_user_add"))
    assert response.status_code == 200
    content = response.content.decode()
    assert 'name="email"' in content
    assert 'name="password1"' in content
    assert 'name="password2"' in content
    assert 'name="first_name"' not in content
    assert 'name="is_staff"' not in content
    assert 'name="is_active"' not in content


# ---- Inline rendering ----------------------------------------------------


@pytest.mark.django_db
def test_org_changeform_renders_membership_inline(
    admin_client: Client,
) -> None:
    org = OrganizationFactory()
    OrganizationMembershipFactory(organization=org, role=Role.ADMIN)
    response = admin_client.get(
        reverse("admin:core_organization_change", args=[org.pk])
    )
    assert response.status_code == 200
    content = response.content.decode()
    # Inline management form prefix uses related_name.
    assert 'name="organization_memberships-TOTAL_FORMS"' in content


@pytest.mark.django_db
def test_location_changeform_renders_membership_inline(
    admin_client: Client,
) -> None:
    location = LocationFactory()
    LocationMembershipFactory(location=location)
    response = admin_client.get(
        reverse("admin:core_location_change", args=[location.pk])
    )
    assert response.status_code == 200
    content = response.content.decode()
    assert 'name="location_memberships-TOTAL_FORMS"' in content


# ---- Invariant: OrganizationMembership change form ------------------------


def _membership_payload(
    m: OrganizationMembership,
    **overrides: Any,  # noqa: ANN401
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "user": str(m.user.pk),
        "organization": str(m.organization.pk),
        "role": m.role,
        "_save": "Save",
    }
    if m.is_active:
        payload["is_active"] = "on"
    payload.update(overrides)
    # is_active checkbox: presence = True, absence = False.
    if "is_active" in overrides and overrides["is_active"] in ("", False):
        payload.pop("is_active", None)
    return payload


@pytest.mark.django_db
def test_admin_blocks_deactivating_last_admin_membership(
    admin_client: Client,
) -> None:
    org = OrganizationFactory()
    m = OrganizationMembershipFactory(organization=org, role=Role.ADMIN)
    response = admin_client.post(
        reverse("admin:core_organizationmembership_change", args=[m.pk]),
        data=_membership_payload(m, is_active=""),
    )
    assert response.status_code == 200  # form re-rendered, not redirect
    m.refresh_from_db()
    assert m.is_active is True
    assert b"would have no active ADMIN" in response.content


@pytest.mark.django_db
def test_admin_blocks_demoting_last_admin_to_operator(
    admin_client: Client,
) -> None:
    org = OrganizationFactory()
    m = OrganizationMembershipFactory(organization=org, role=Role.ADMIN)
    response = admin_client.post(
        reverse("admin:core_organizationmembership_change", args=[m.pk]),
        data=_membership_payload(m, role=Role.OPERATOR),
    )
    assert response.status_code == 200
    m.refresh_from_db()
    assert m.role == Role.ADMIN


@pytest.mark.django_db
def test_admin_deactivates_non_last_admin(admin_client: Client) -> None:
    org = OrganizationFactory()
    m1 = OrganizationMembershipFactory(organization=org, role=Role.ADMIN)
    OrganizationMembershipFactory(organization=org, role=Role.ADMIN)
    response = admin_client.post(
        reverse("admin:core_organizationmembership_change", args=[m1.pk]),
        data=_membership_payload(m1, is_active=""),
    )
    assert response.status_code == 302
    m1.refresh_from_db()
    assert m1.is_active is False


@pytest.mark.django_db
def test_admin_reactivates_inactive_membership(admin_client: Client) -> None:
    m = OrganizationMembershipFactory(role=Role.OPERATOR, is_active=False)
    response = admin_client.post(
        reverse("admin:core_organizationmembership_change", args=[m.pk]),
        data=_membership_payload(m, is_active="on"),
    )
    assert response.status_code == 302
    m.refresh_from_db()
    assert m.is_active is True


# ---- Invariant: User change form -----------------------------------------


def _user_payload(
    user: User,
    **overrides: Any,  # noqa: ANN401
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "email": user.email,
        "password": user.password,
        "first_name": user.first_name,
        "last_name": user.last_name,
        "preferred_language": user.preferred_language,
        "_save": "Save",
    }
    if user.is_active:
        payload["is_active"] = "on"
    if user.is_staff:
        payload["is_staff"] = "on"
    if user.is_superuser:
        payload["is_superuser"] = "on"
    payload.update(overrides)
    if "is_active" in overrides and overrides["is_active"] in ("", False):
        payload.pop("is_active", None)
    return payload


@pytest.mark.django_db
def test_admin_blocks_deactivating_user_who_is_sole_admin(
    admin_client: Client,
) -> None:
    org = OrganizationFactory(slug="acme")
    user = UserFactory()
    OrganizationMembershipFactory(user=user, organization=org, role=Role.ADMIN)
    response = admin_client.post(
        reverse("admin:core_user_change", args=[user.pk]),
        data=_user_payload(user, is_active=""),
    )
    assert response.status_code == 200
    user.refresh_from_db()
    assert user.is_active is True
    assert b"acme" in response.content


# ---- Invariant: inline on Organization changeform ------------------------


def _org_payload_with_inline(
    org: Organization,
    memberships: list[OrganizationMembership],
    inline_overrides: dict[int, dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Build POST payload for an Organization change form, including the
    OrganizationMembership inline formset."""
    inline_overrides = inline_overrides or {}
    payload: dict[str, Any] = {
        "name": org.name,
        "slug": org.slug,
        "country": str(org.country),
        "default_timezone": str(org.default_timezone),
        "default_currency": str(org.default_currency),
        "default_language": org.default_language,
        "vat_number": org.vat_number,
        "billing_email": org.billing_email,
        "_save": "Save",
    }
    if org.is_active:
        payload["is_active"] = "on"
    prefix = "organization_memberships"
    payload[f"{prefix}-TOTAL_FORMS"] = str(len(memberships))
    payload[f"{prefix}-INITIAL_FORMS"] = str(len(memberships))
    payload[f"{prefix}-MIN_NUM_FORMS"] = "0"
    payload[f"{prefix}-MAX_NUM_FORMS"] = "1000"
    for i, m in enumerate(memberships):
        payload[f"{prefix}-{i}-id"] = str(m.pk)
        payload[f"{prefix}-{i}-organization"] = str(org.pk)
        payload[f"{prefix}-{i}-user"] = str(m.user.pk)
        payload[f"{prefix}-{i}-role"] = m.role
        if m.is_active:
            payload[f"{prefix}-{i}-is_active"] = "on"
        if m.created_by is not None:
            payload[f"{prefix}-{i}-created_by"] = str(m.created_by.pk)
        for key, value in inline_overrides.get(i, {}).items():
            field_key = f"{prefix}-{i}-{key}"
            if value in ("", False):
                payload.pop(field_key, None)
            else:
                payload[field_key] = value
    return payload


@pytest.mark.django_db
def test_org_inline_blocks_deactivating_last_admin(
    admin_client: Client,
) -> None:
    org = OrganizationFactory()
    m = OrganizationMembershipFactory(organization=org, role=Role.ADMIN)
    response = admin_client.post(
        reverse("admin:core_organization_change", args=[org.pk]),
        data=_org_payload_with_inline(
            org, [m], inline_overrides={0: {"is_active": ""}}
        ),
    )
    assert response.status_code == 200  # form re-rendered
    m.refresh_from_db()
    assert m.is_active is True
    assert b"would have no active ADMIN" in response.content


# ---- Symmetry checks: registered models ---------------------------------


def test_all_foundation_models_are_registered() -> None:
    from django.contrib import admin as django_admin

    for model in (
        Organization,
        User,
        OrganizationMembership,
        Location,
        LocationMembership,
    ):
        assert django_admin.site.is_registered(model), (
            f"{model.__name__} not registered in admin"
        )
