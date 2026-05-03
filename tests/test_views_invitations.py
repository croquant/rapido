from datetime import timedelta

import pytest
from django.core import mail
from django.test import Client
from django.utils import timezone

from core.models import (
    Invitation,
    LocationMembership,
    Organization,
    OrganizationMembership,
    Role,
    User,
)
from core.services.tokens import make_invite_token
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


# ---- accept -----------------------------------------------------------------


def _make_invite(
    *,
    organization: Organization | None = None,
    email: str = "invitee@example.be",
    role: str = Role.ADMIN,
    locations: list | None = None,
) -> Invitation:
    org = organization or OrganizationFactory()
    inviter = OrganizationMembershipFactory(
        role=Role.ADMIN, organization=org
    ).user
    invite = InvitationFactory(
        organization=org, email=email, role=role, created_by=inviter
    )
    if locations:
        invite.locations.set(locations)
    return invite


def _accept_url(token: str) -> str:
    return f"/invite/{token}/"


@pytest.mark.django_db
def test_accept_get_new_user_renders_password_form() -> None:
    invite = _make_invite()
    token = make_invite_token(invite)

    response = Client().get(_accept_url(token))

    assert response.status_code == 200
    assert b'name="new_password"' in response.content
    assert b'name="confirm_password"' in response.content


@pytest.mark.django_db
def test_accept_get_existing_user_renders_no_password() -> None:
    org = OrganizationFactory()
    UserFactory(email="invitee@example.be")
    invite = _make_invite(organization=org, email="invitee@example.be")
    token = make_invite_token(invite)

    response = Client().get(_accept_url(token))

    assert response.status_code == 200
    assert b'name="new_password"' not in response.content


@pytest.mark.django_db
def test_accept_post_new_user_creates_user_and_memberships() -> None:
    org = OrganizationFactory()
    location = LocationFactory(organization=org)
    invite = _make_invite(
        organization=org,
        email="newhire@example.be",
        role=Role.OPERATOR,
        locations=[location],
    )
    token = make_invite_token(invite)
    client = Client()

    response = client.post(
        _accept_url(token),
        {"new_password": "Sup3rSecret!", "confirm_password": "Sup3rSecret!"},
    )

    assert response.status_code == 302
    user = User.objects.get(email="newhire@example.be")
    assert OrganizationMembership.objects.filter(
        user=user, organization=org, is_active=True, role=Role.OPERATOR
    ).exists()
    assert LocationMembership.objects.filter(
        user=user, location=location, is_active=True
    ).exists()
    invite.refresh_from_db()
    assert invite.accepted_at is not None
    assert response.wsgi_request.user.is_authenticated
    assert response.wsgi_request.user.pk == user.pk


@pytest.mark.django_db
def test_accept_post_redirects_per_login_rule_single_org() -> None:
    org = OrganizationFactory(slug="acme")
    invite = _make_invite(organization=org, email="newhire@example.be")
    token = make_invite_token(invite)

    response = Client().post(
        _accept_url(token),
        {"new_password": "Sup3rSecret!", "confirm_password": "Sup3rSecret!"},
    )

    assert response.status_code == 302
    assert response.headers["Location"] == "/o/acme/"


@pytest.mark.django_db
def test_accept_post_existing_user_creates_memberships_only() -> None:
    org = OrganizationFactory()
    user = UserFactory(email="existing@example.be")
    original_hash = user.password
    invite = _make_invite(organization=org, email="existing@example.be")
    token = make_invite_token(invite)

    response = Client().post(_accept_url(token))

    assert response.status_code == 302
    assert User.objects.filter(email="existing@example.be").count() == 1
    user.refresh_from_db()
    assert user.password == original_hash
    assert OrganizationMembership.objects.filter(
        user=user, organization=org, is_active=True
    ).exists()
    invite.refresh_from_db()
    assert invite.accepted_at is not None


@pytest.mark.django_db
def test_accept_get_expired_renders_error_200() -> None:
    invite = _make_invite()
    invite.expires_at = timezone.now() - timedelta(days=1)
    invite.save(update_fields=["expires_at"])
    token = make_invite_token(invite)

    response = Client().get(_accept_url(token))

    assert response.status_code == 200
    assert b"invalid or has expired" in response.content


@pytest.mark.django_db
def test_accept_tampered_token_renders_error() -> None:
    invite = _make_invite()
    token = make_invite_token(invite)
    tampered = token[:-1] + ("A" if token[-1] != "A" else "B")

    response = Client().get(_accept_url(tampered))

    assert response.status_code == 200
    assert b"invalid or has expired" in response.content


@pytest.mark.django_db
def test_accept_already_accepted_renders_error() -> None:
    invite = _make_invite()
    invite.accepted_at = timezone.now()
    invite.save(update_fields=["accepted_at"])
    token = make_invite_token(invite)

    response = Client().get(_accept_url(token))

    assert response.status_code == 200
    assert b"already been used" in response.content


@pytest.mark.django_db
def test_accept_revoked_renders_error() -> None:
    invite = _make_invite()
    invite.revoked_at = timezone.now()
    invite.save(update_fields=["revoked_at"])
    token = make_invite_token(invite)

    response = Client().get(_accept_url(token))

    assert response.status_code == 200
    assert b"revoked" in response.content


@pytest.mark.django_db
def test_accept_stale_locations_get_renders_error_no_mutations() -> None:
    org = OrganizationFactory()
    location = LocationFactory(organization=org)
    invite = _make_invite(
        organization=org,
        email="newhire@example.be",
        role=Role.OPERATOR,
        locations=[location],
    )
    location.is_active = False
    location.save(update_fields=["is_active"])
    token = make_invite_token(invite)

    response = Client().get(_accept_url(token))

    assert response.status_code == 200
    assert b"no longer active" in response.content
    assert not User.objects.filter(email="newhire@example.be").exists()
    assert not OrganizationMembership.objects.filter(
        organization=org, user__email="newhire@example.be"
    ).exists()


@pytest.mark.django_db
def test_accept_stale_locations_post_does_not_mutate() -> None:
    org = OrganizationFactory()
    location = LocationFactory(organization=org)
    invite = _make_invite(
        organization=org,
        email="newhire@example.be",
        role=Role.OPERATOR,
        locations=[location],
    )
    location.is_active = False
    location.save(update_fields=["is_active"])
    token = make_invite_token(invite)

    response = Client().post(
        _accept_url(token),
        {"new_password": "Sup3rSecret!", "confirm_password": "Sup3rSecret!"},
    )

    assert response.status_code == 200
    assert not User.objects.filter(email="newhire@example.be").exists()
    invite.refresh_from_db()
    assert invite.accepted_at is None


@pytest.mark.django_db
def test_accept_post_atomic_rollback_on_service_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    org = OrganizationFactory()
    location = LocationFactory(organization=org)
    invite = _make_invite(
        organization=org,
        email="newhire@example.be",
        role=Role.OPERATOR,
        locations=[location],
    )
    token = make_invite_token(invite)

    from core.services import invitation as invitation_service

    real_create = LocationMembership.objects.create

    def boom(*args: object, **kwargs: object) -> None:  # noqa: ARG001
        raise RuntimeError("boom")

    monkeypatch.setattr(
        LocationMembership.objects, "create", boom, raising=True
    )
    assert invitation_service  # silence unused-name lint

    with pytest.raises(RuntimeError):
        Client().post(
            _accept_url(token),
            {
                "new_password": "Sup3rSecret!",
                "confirm_password": "Sup3rSecret!",
            },
        )

    monkeypatch.setattr(
        LocationMembership.objects, "create", real_create, raising=True
    )
    assert not User.objects.filter(email="newhire@example.be").exists()
    assert not OrganizationMembership.objects.filter(
        organization=org, user__email="newhire@example.be"
    ).exists()
    invite.refresh_from_db()
    assert invite.accepted_at is None


@pytest.mark.django_db
def test_accept_weak_password_returns_422_with_errors() -> None:
    invite = _make_invite(email="newhire@example.be")
    token = make_invite_token(invite)

    response = Client().post(
        _accept_url(token),
        {"new_password": "short", "confirm_password": "short"},
    )

    assert response.status_code == 422
    assert not User.objects.filter(email="newhire@example.be").exists()


@pytest.mark.django_db
def test_accept_password_mismatch_returns_422() -> None:
    invite = _make_invite(email="newhire@example.be")
    token = make_invite_token(invite)

    response = Client().post(
        _accept_url(token),
        {
            "new_password": "Sup3rSecret!",
            "confirm_password": "DifferentPass1!",
        },
    )

    assert response.status_code == 422
    assert not User.objects.filter(email="newhire@example.be").exists()


@pytest.mark.django_db
def test_accept_authenticated_matching_email_proceeds() -> None:
    org = OrganizationFactory()
    user = UserFactory(email="existing@example.be")
    invite = _make_invite(organization=org, email="existing@example.be")
    token = make_invite_token(invite)
    client = Client()
    client.force_login(user)

    get_response = client.get(_accept_url(token))
    assert get_response.status_code == 200
    assert b'name="new_password"' not in get_response.content

    post_response = client.post(_accept_url(token))
    assert post_response.status_code == 302
    assert OrganizationMembership.objects.filter(
        user=user, organization=org, is_active=True
    ).exists()


@pytest.mark.django_db
def test_accept_get_mismatched_email_does_not_logout() -> None:
    # GET must be side-effect-free: a logout-on-GET on this public URL would
    # be a CSRF-style logout vector (e.g., <img src="/invite/<token>/">).
    other_user = UserFactory(email="someone-else@example.be")
    invite = _make_invite(email="newhire@example.be")
    token = make_invite_token(invite)
    client = Client()
    client.force_login(other_user)

    response = client.get(_accept_url(token))

    assert response.status_code == 200
    assert response.wsgi_request.user.is_authenticated
    assert response.wsgi_request.user.pk == other_user.pk
    assert b'name="new_password"' in response.content


@pytest.mark.django_db
def test_accept_post_mismatched_email_logs_out_and_processes() -> None:
    other_user = UserFactory(email="someone-else@example.be")
    invite = _make_invite(email="newhire@example.be")
    token = make_invite_token(invite)
    client = Client()
    client.force_login(other_user)

    response = client.post(
        _accept_url(token),
        {"new_password": "Sup3rSecret!", "confirm_password": "Sup3rSecret!"},
    )

    assert response.status_code == 302
    new_user = User.objects.get(email="newhire@example.be")
    assert response.wsgi_request.user.pk == new_user.pk


@pytest.mark.django_db
def test_accept_already_member_renders_error() -> None:
    org = OrganizationFactory()
    user = UserFactory(email="existing@example.be")
    OrganizationMembershipFactory(
        user=user, organization=org, role=Role.ADMIN, is_active=True
    )
    invite = _make_invite(organization=org, email="existing@example.be")
    token = make_invite_token(invite)

    response = Client().get(_accept_url(token))

    assert response.status_code == 200
    assert b"already a member" in response.content
