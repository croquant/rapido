from typing import Any
from unittest.mock import patch

import pytest
from django.contrib.auth import get_user
from django.test import Client
from django.urls import reverse

from core.models import Role, User
from tests.factories import (
    LocationFactory,
    LocationMembershipFactory,
    OrganizationFactory,
    OrganizationMembershipFactory,
    UserFactory,
)

_Capture = Any


# ---------------------------------------------------------------------------
# GET /login/
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_get_renders_200() -> None:
    client = Client()
    response = client.get(reverse("core:login"))
    assert response.status_code == 200


@pytest.mark.django_db
def test_get_authenticated_redirects_via_rule() -> None:
    user = UserFactory()
    org = OrganizationFactory(slug="acme")
    OrganizationMembershipFactory(user=user, organization=org, role=Role.ADMIN)
    client = Client()
    client.force_login(user)

    response = client.get(reverse("core:login"))

    assert response.status_code == 302
    assert response["Location"] == "/o/acme/"


# ---------------------------------------------------------------------------
# POST /login/ - happy paths via the redirect rule
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_post_single_admin_redirects_to_org_dashboard() -> None:
    user = UserFactory(email="admin@example.be")
    org = OrganizationFactory(slug="acme")
    OrganizationMembershipFactory(user=user, organization=org, role=Role.ADMIN)
    client = Client()

    response = client.post(
        reverse("core:login"),
        data={"email": "admin@example.be", "password": "password"},
    )

    assert response.status_code == 302
    assert response["Location"] == "/o/acme/"
    auth_user = get_user(client)
    assert auth_user.is_authenticated
    assert auth_user.pk == user.pk


@pytest.mark.django_db
def test_post_multiple_memberships_redirects_to_picker() -> None:
    user = UserFactory(email="multi@example.be")
    OrganizationMembershipFactory(user=user, role=Role.ADMIN)
    OrganizationMembershipFactory(user=user, role=Role.ADMIN)
    client = Client()

    response = client.post(
        reverse("core:login"),
        data={"email": "multi@example.be", "password": "password"},
    )

    assert response.status_code == 302
    assert response["Location"] == "/orgs/"


@pytest.mark.django_db
def test_post_operator_single_location_redirects_to_pos() -> None:
    user = UserFactory(email="op@example.be")
    org = OrganizationFactory(slug="acme")
    OrganizationMembershipFactory(
        user=user, organization=org, role=Role.OPERATOR
    )
    location = LocationFactory(organization=org, slug="downtown")
    LocationMembershipFactory(user=user, location=location)
    client = Client()

    response = client.post(
        reverse("core:login"),
        data={"email": "op@example.be", "password": "password"},
    )

    assert response.status_code == 302
    assert response["Location"] == "/o/acme/l/downtown/pos/"


@pytest.mark.django_db
def test_post_operator_multiple_locations_redirects_to_org() -> None:
    user = UserFactory(email="op2@example.be")
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
    client = Client()

    response = client.post(
        reverse("core:login"),
        data={"email": "op2@example.be", "password": "password"},
    )

    assert response.status_code == 302
    assert response["Location"] == "/o/acme/"


@pytest.mark.django_db
def test_post_operator_no_locations_redirects_to_org() -> None:
    user = UserFactory(email="op3@example.be")
    org = OrganizationFactory(slug="acme")
    OrganizationMembershipFactory(
        user=user, organization=org, role=Role.OPERATOR
    )
    client = Client()

    response = client.post(
        reverse("core:login"),
        data={"email": "op3@example.be", "password": "password"},
    )

    assert response.status_code == 302
    assert response["Location"] == "/o/acme/"


# ---------------------------------------------------------------------------
# POST /login/ - rejection paths (no enumeration)
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_post_unknown_email_returns_generic_error() -> None:
    client = Client()
    response = client.post(
        reverse("core:login"),
        data={"email": "nobody@example.be", "password": "password"},
    )

    assert response.status_code == 200
    form = response.context["form"]
    assert "Invalid email or password" in str(form.non_field_errors())
    assert form.unverified_email is None
    assert reverse("core:resend_verification").encode() not in response.content


@pytest.mark.django_db
def test_post_wrong_password_returns_generic_error() -> None:
    UserFactory(email="user@example.be")
    client = Client()
    response = client.post(
        reverse("core:login"),
        data={"email": "user@example.be", "password": "wrong"},
    )

    assert response.status_code == 200
    form = response.context["form"]
    assert "Invalid email or password" in str(form.non_field_errors())
    assert form.unverified_email is None
    assert reverse("core:resend_verification").encode() not in response.content


@pytest.mark.django_db
def test_post_inactive_user_shows_resend() -> None:
    user = UserFactory(email="pending@example.be", is_active=False)
    OrganizationMembershipFactory(user=user, role=Role.ADMIN)
    client = Client()

    response = client.post(
        reverse("core:login"),
        data={"email": "pending@example.be", "password": "password"},
    )

    assert response.status_code == 200
    form = response.context["form"]
    assert form.unverified_email == "pending@example.be"
    assert "check your inbox" in str(form.non_field_errors()).lower()
    assert reverse("core:resend_verification").encode() in response.content
    auth_user = get_user(client)
    assert not auth_user.is_authenticated


@pytest.mark.django_db
def test_post_email_normalized_lowercase() -> None:
    user = UserFactory(email="case@example.be")
    org = OrganizationFactory(slug="acme")
    OrganizationMembershipFactory(user=user, organization=org, role=Role.ADMIN)
    client = Client()

    response = client.post(
        reverse("core:login"),
        data={"email": "CASE@Example.BE", "password": "password"},
    )

    assert response.status_code == 302
    assert response["Location"] == "/o/acme/"


# ---------------------------------------------------------------------------
# ?next= handling
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_post_safe_next_overrides_redirect_rule() -> None:
    user = UserFactory(email="admin@example.be")
    org = OrganizationFactory(slug="acme")
    OrganizationMembershipFactory(user=user, organization=org, role=Role.ADMIN)
    client = Client()

    response = client.post(
        reverse("core:login"),
        data={
            "email": "admin@example.be",
            "password": "password",
            "next": "/o/acme/menu/",
        },
    )

    assert response.status_code == 302
    assert response["Location"] == "/o/acme/menu/"


@pytest.mark.django_db
def test_post_unsafe_next_falls_through_to_rule() -> None:
    user = UserFactory(email="admin@example.be")
    org = OrganizationFactory(slug="acme")
    OrganizationMembershipFactory(user=user, organization=org, role=Role.ADMIN)
    client = Client()

    response = client.post(
        reverse("core:login"),
        data={
            "email": "admin@example.be",
            "password": "password",
            "next": "https://evil.example.com/",
        },
    )

    assert response.status_code == 302
    assert response["Location"] == "/o/acme/"


@pytest.mark.django_db
def test_get_with_next_renders_hidden_input() -> None:
    client = Client()
    response = client.get(reverse("core:login") + "?next=/o/acme/menu/")

    assert response.status_code == 200
    assert response.context["next"] == "/o/acme/menu/"
    assert b'name="next"' in response.content
    assert b"/o/acme/menu/" in response.content


# ---------------------------------------------------------------------------
# /logout/
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_logout_post_clears_session_and_redirects() -> None:
    user = UserFactory()
    client = Client()
    client.force_login(user)
    assert get_user(client).is_authenticated

    response = client.post(reverse("core:logout"))

    assert response.status_code == 302
    assert response["Location"] == "/"
    assert not get_user(client).is_authenticated


@pytest.mark.django_db
def test_logout_get_returns_405() -> None:
    user = UserFactory()
    client = Client()
    client.force_login(user)

    response = client.get(reverse("core:logout"))

    assert response.status_code == 405
    assert get_user(client).is_authenticated


@pytest.mark.django_db
def test_logout_anonymous_post_is_idempotent() -> None:
    client = Client()
    response = client.post(reverse("core:logout"))

    assert response.status_code == 302
    assert response["Location"] == "/"


# ---------------------------------------------------------------------------
# /resend-verification/
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_resend_inactive_user_enqueues_email(
    django_capture_on_commit_callbacks: _Capture,
) -> None:
    user = UserFactory(email="pending@example.be", is_active=False)
    OrganizationMembershipFactory(user=user, role=Role.ADMIN)
    client = Client()

    with patch("core.services.resend.send_templated") as send:
        with django_capture_on_commit_callbacks(execute=True) as callbacks:
            response = client.post(
                reverse("core:resend_verification"),
                data={"email": "pending@example.be"},
            )
        assert response.status_code == 200
        assert "auth/verify_resent.html" in [t.name for t in response.templates]
        assert len(callbacks) == 1
        send.assert_called_once()
        args, kwargs = send.call_args
        assert args == ("email/verify",)
        assert kwargs["to"].pk == user.pk
        assert kwargs["context"]["verify_url"].startswith("http")


@pytest.mark.django_db
def test_resend_active_user_no_email(
    django_capture_on_commit_callbacks: _Capture,
) -> None:
    UserFactory(email="active@example.be", is_active=True)
    client = Client()

    with patch("core.services.resend.send_templated") as send:
        with django_capture_on_commit_callbacks(execute=True) as callbacks:
            response = client.post(
                reverse("core:resend_verification"),
                data={"email": "active@example.be"},
            )
        assert response.status_code == 200
        assert "auth/verify_resent.html" in [t.name for t in response.templates]
        assert len(callbacks) == 0
        send.assert_not_called()


@pytest.mark.django_db
def test_resend_unknown_email_no_email(
    django_capture_on_commit_callbacks: _Capture,
) -> None:
    client = Client()
    with patch("core.services.resend.send_templated") as send:
        with django_capture_on_commit_callbacks(execute=True) as callbacks:
            response = client.post(
                reverse("core:resend_verification"),
                data={"email": "nobody@example.be"},
            )
        assert response.status_code == 200
        assert "auth/verify_resent.html" in [t.name for t in response.templates]
        assert len(callbacks) == 0
        send.assert_not_called()


@pytest.mark.django_db
def test_resend_missing_email_no_email(
    django_capture_on_commit_callbacks: _Capture,
) -> None:
    client = Client()
    with patch("core.services.resend.send_templated") as send:
        with django_capture_on_commit_callbacks(execute=True) as callbacks:
            response = client.post(reverse("core:resend_verification"))
        assert response.status_code == 200
        assert len(callbacks) == 0
        send.assert_not_called()


@pytest.mark.django_db
def test_resend_get_returns_405() -> None:
    client = Client()
    response = client.get(reverse("core:resend_verification"))
    assert response.status_code == 405


@pytest.mark.django_db
def test_resend_case_insensitive_email_match(
    django_capture_on_commit_callbacks: _Capture,
) -> None:
    UserFactory(email="pending@example.be", is_active=False)
    client = Client()

    with patch("core.services.resend.send_templated") as send:
        with django_capture_on_commit_callbacks(execute=True):
            response = client.post(
                reverse("core:resend_verification"),
                data={"email": "PENDING@Example.BE"},
            )
        assert response.status_code == 200
        send.assert_called_once()
        sent_to = send.call_args.kwargs["to"]
        assert isinstance(sent_to, User)
        assert sent_to.email == "pending@example.be"
