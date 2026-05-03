import pytest
from django.test import Client

from core.models import Organization, Role
from core.services.invitation import create_invitation
from tests.factories import OrganizationFactory, OrganizationMembershipFactory


def _url(slug: str) -> str:
    return f"/o/{slug}/settings/organization/"


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


def _post_data(org: Organization, **overrides: str) -> dict[str, str]:
    data = {
        "name": org.name,
        "country": str(org.country),
        "vat_number": org.vat_number,
        "default_language": org.default_language,
    }
    data.update(overrides)
    return data


# ---- anonymous --------------------------------------------------------------


@pytest.mark.django_db
def test_anonymous_returns_404() -> None:
    org = OrganizationFactory()
    response = Client().get(_url(org.slug))
    assert response.status_code == 404


# ---- operator forbidden -----------------------------------------------------


@pytest.mark.django_db
def test_operator_forbidden() -> None:
    membership = OrganizationMembershipFactory(role=Role.OPERATOR)
    client = Client()
    client.force_login(membership.user)
    url = _url(membership.organization.slug)

    assert client.get(url).status_code == 403
    assert (
        client.post(url, _post_data(membership.organization)).status_code == 403
    )


# ---- admin GET --------------------------------------------------------------


@pytest.mark.django_db
def test_admin_get_renders_form_without_slug_field() -> None:
    client, org = _admin_client()

    response = client.get(_url(org.slug))

    assert response.status_code == 200
    body = response.content.decode()
    assert org.name in body
    # Slug shown read-only.
    assert f"<code>{org.slug}</code>" in body
    # No editable slug input.
    assert 'name="slug"' not in body
    # Editable fields are present.
    assert 'name="name"' in body
    assert 'name="country"' in body
    assert 'name="vat_number"' in body
    assert 'name="default_language"' in body


# ---- admin POST -------------------------------------------------------------


@pytest.mark.django_db
def test_admin_post_updates_fields_and_redirects() -> None:
    client, org = _admin_client()

    response = client.post(
        _url(org.slug),
        _post_data(
            org,
            name="Renamed Org",
            default_language="fr-BE",
        ),
    )

    assert response.status_code == 302
    assert response["Location"] == _url(org.slug)
    org.refresh_from_db()
    assert org.name == "Renamed Org"
    assert org.default_language == "fr-BE"


@pytest.mark.django_db
def test_admin_post_invalid_vat_returns_field_error() -> None:
    client, org = _admin_client()
    original_vat = org.vat_number

    response = client.post(
        _url(org.slug),
        _post_data(org, vat_number="BE000"),
    )

    assert response.status_code == 200
    form = response.context["form"]
    assert "vat_number" in form.errors
    org.refresh_from_db()
    assert org.vat_number == original_vat


@pytest.mark.django_db
def test_admin_cannot_edit_other_org() -> None:
    client, _ = _admin_client()
    other = OrganizationFactory()

    assert client.get(_url(other.slug)).status_code == 404
    assert client.post(_url(other.slug), _post_data(other)).status_code == 404


# ---- default_language propagates to subsequent emails -----------------------


@pytest.mark.django_db
def test_default_language_change_reflected_in_invitation_email(
    mailoutbox: list,
    django_capture_on_commit_callbacks,  # noqa: ANN001
) -> None:
    client, org = _admin_client()

    response = client.post(
        _url(org.slug),
        _post_data(org, default_language="fr-BE"),
    )
    assert response.status_code == 302

    org.refresh_from_db()
    membership = OrganizationMembershipFactory(
        role=Role.ADMIN, organization=org
    )
    with django_capture_on_commit_callbacks(execute=True):
        create_invitation(
            organization=org,
            email="newcomer@example.be",
            role=Role.ADMIN,
            created_by=membership.user,
        )

    msg = mailoutbox[-1]
    html = str(msg.alternatives[0][0])
    assert 'lang="fr-be"' in html.lower()
