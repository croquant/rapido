import pytest
from django.core import mail
from django.test import Client
from django.utils import timezone

from core.models import Invitation, Organization, OrganizationMembership, Role
from tests.factories import (
    InvitationFactory,
    LocationFactory,
    OrganizationFactory,
    OrganizationMembershipFactory,
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


def _routes(slug: str, pk: int = 1) -> dict[str, str]:
    base = f"/o/{slug}/settings/invitations"
    return {
        "create": f"{base}/",
        "resend": f"{base}/{pk}/resend/",
        "revoke": f"{base}/{pk}/revoke/",
    }


# ---- create -----------------------------------------------------------------


@pytest.mark.django_db
def test_admin_can_create_invitation_and_email_sent(
    django_capture_on_commit_callbacks,  # noqa: ANN001
) -> None:
    client, admin = _admin_client()
    org = admin.organization
    location = LocationFactory(organization=org)
    mail.outbox = []

    with django_capture_on_commit_callbacks(execute=True):
        response = client.post(
            _routes(org.slug)["create"],
            {
                "email": "newhire@example.be",
                "role": "OPERATOR",
                "locations": [str(location.pk)],
            },
            HTTP_HX_REQUEST="true",
        )

    assert response.status_code == 204
    assert response.headers["HX-Redirect"].endswith(
        f"/o/{org.slug}/settings/members/"
    )
    invite = Invitation.objects.get(
        organization=org, email="newhire@example.be"
    )
    assert invite.role == Role.OPERATOR
    assert list(invite.locations.all()) == [location]
    assert len(mail.outbox) == 1


@pytest.mark.django_db
def test_create_admin_no_locations_succeeds() -> None:
    client, admin = _admin_client()

    response = client.post(
        _routes(admin.organization.slug)["create"],
        {"email": "admin2@example.be", "role": "ADMIN"},
    )

    assert response.status_code in (302, 204)
    assert Invitation.objects.filter(email="admin2@example.be").exists()


@pytest.mark.django_db
def test_create_operator_without_locations_returns_422() -> None:
    client, admin = _admin_client()

    response = client.post(
        _routes(admin.organization.slug)["create"],
        {"email": "no-loc@example.be", "role": "OPERATOR"},
        HTTP_HX_REQUEST="true",
    )

    assert response.status_code == 422
    assert not Invitation.objects.filter(email="no-loc@example.be").exists()


@pytest.mark.django_db
def test_create_already_member_returns_422() -> None:
    client, admin = _admin_client()
    org = admin.organization
    existing = OrganizationMembershipFactory(
        role=Role.OPERATOR, organization=org
    )

    response = client.post(
        _routes(org.slug)["create"],
        {"email": existing.user.email, "role": "ADMIN"},
        HTTP_HX_REQUEST="true",
    )

    assert response.status_code == 422
    assert not Invitation.objects.filter(
        organization=org, email=existing.user.email
    ).exists()


@pytest.mark.django_db
def test_create_pending_exists_returns_422() -> None:
    client, admin = _admin_client()
    org = admin.organization
    InvitationFactory(
        organization=org,
        email="dup@example.be",
        role=Role.ADMIN,
        created_by=admin.user,
    )

    response = client.post(
        _routes(org.slug)["create"],
        {"email": "dup@example.be", "role": "ADMIN"},
        HTTP_HX_REQUEST="true",
    )

    assert response.status_code == 422
    assert (
        Invitation.objects.filter(
            organization=org, email="dup@example.be"
        ).count()
        == 1
    )


# ---- resend -----------------------------------------------------------------


@pytest.mark.django_db
def test_resend_extends_expiry_and_sends_email(
    django_capture_on_commit_callbacks,  # noqa: ANN001
) -> None:
    client, admin = _admin_client()
    org = admin.organization
    location = LocationFactory(organization=org)
    invite = InvitationFactory(
        organization=org, role=Role.OPERATOR, created_by=admin.user
    )
    invite.locations.set([location])
    original_expiry = invite.expires_at
    mail.outbox = []

    with django_capture_on_commit_callbacks(execute=True):
        response = client.post(
            _routes(org.slug, invite.pk)["resend"],
            HTTP_HX_REQUEST="true",
        )

    assert response.status_code == 200
    invite.refresh_from_db()
    assert invite.expires_at > original_expiry
    assert len(mail.outbox) == 1


@pytest.mark.django_db
def test_resend_revoked_invitation_returns_422() -> None:
    client, admin = _admin_client()
    org = admin.organization
    invite = InvitationFactory(
        organization=org, role=Role.ADMIN, created_by=admin.user
    )
    invite.revoked_at = timezone.now()
    invite.save(update_fields=["revoked_at"])

    response = client.post(
        _routes(org.slug, invite.pk)["resend"],
        HTTP_HX_REQUEST="true",
    )

    assert response.status_code == 422
    assert response.headers.get("HX-Trigger") == "invitations:resend_failed"


@pytest.mark.django_db
def test_resend_accepted_invitation_returns_422() -> None:
    client, admin = _admin_client()
    org = admin.organization
    invite = InvitationFactory(
        organization=org, role=Role.ADMIN, created_by=admin.user
    )
    invite.accepted_at = timezone.now()
    invite.save(update_fields=["accepted_at"])

    response = client.post(
        _routes(org.slug, invite.pk)["resend"],
        HTTP_HX_REQUEST="true",
    )

    assert response.status_code == 422


# ---- revoke -----------------------------------------------------------------


@pytest.mark.django_db
def test_revoke_marks_invitation_revoked_and_returns_refresh() -> None:
    client, admin = _admin_client()
    org = admin.organization
    invite = InvitationFactory(
        organization=org, role=Role.ADMIN, created_by=admin.user
    )

    response = client.post(
        _routes(org.slug, invite.pk)["revoke"],
        HTTP_HX_REQUEST="true",
    )

    assert response.status_code == 204
    assert response.headers.get("HX-Refresh") == "true"
    invite.refresh_from_db()
    assert invite.revoked_at is not None


@pytest.mark.django_db
def test_revoke_idempotent() -> None:
    client, admin = _admin_client()
    org = admin.organization
    invite = InvitationFactory(
        organization=org, role=Role.ADMIN, created_by=admin.user
    )

    first = client.post(
        _routes(org.slug, invite.pk)["revoke"], HTTP_HX_REQUEST="true"
    )
    invite.refresh_from_db()
    first_revoked_at = invite.revoked_at
    second = client.post(
        _routes(org.slug, invite.pk)["revoke"], HTTP_HX_REQUEST="true"
    )

    assert first.status_code == 204
    assert second.status_code == 204
    invite.refresh_from_db()
    assert invite.revoked_at == first_revoked_at


# ---- cross-org -------------------------------------------------------------


@pytest.mark.django_db
def test_cross_org_resend_404() -> None:
    client, admin = _admin_client()
    other_org = OrganizationFactory()
    other_invite = InvitationFactory(organization=other_org, role=Role.ADMIN)

    response = client.post(
        _routes(admin.organization.slug, other_invite.pk)["resend"],
        HTTP_HX_REQUEST="true",
    )
    assert response.status_code == 404


@pytest.mark.django_db
def test_cross_org_revoke_404() -> None:
    client, admin = _admin_client()
    other_invite = InvitationFactory(
        organization=OrganizationFactory(), role=Role.ADMIN
    )

    response = client.post(
        _routes(admin.organization.slug, other_invite.pk)["revoke"],
        HTTP_HX_REQUEST="true",
    )
    assert response.status_code == 404


# ---- operator forbidden -----------------------------------------------------


@pytest.mark.django_db
def test_operator_forbidden_on_create() -> None:
    op = OrganizationMembershipFactory(role=Role.OPERATOR)
    client = Client()
    client.force_login(op.user)

    response = client.post(
        _routes(op.organization.slug)["create"],
        {"email": "no@example.be", "role": "OPERATOR"},
    )
    assert response.status_code == 403


# ---- method guards ----------------------------------------------------------


@pytest.mark.django_db
def test_get_on_create_returns_405() -> None:
    client, admin = _admin_client()
    response = client.get(_routes(admin.organization.slug)["create"])
    assert response.status_code == 405
