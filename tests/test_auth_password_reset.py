import re
from typing import Any
from unittest.mock import patch

import pytest
from django.contrib.auth import get_user
from django.core import signing
from django.test import Client
from django.urls import reverse

from core.models import Role
from core.services.password_reset import make_password_reset_token
from tests.factories import (
    OrganizationFactory,
    OrganizationMembershipFactory,
    UserFactory,
)

_Capture = Any

# ---------------------------------------------------------------------------
# Request flow (issue #58)
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_request_get_renders_form() -> None:
    response = Client().get(reverse("core:password_reset_request"))
    assert response.status_code == 200
    assert "auth/password_reset_request.html" in [
        t.name for t in response.templates
    ]


@pytest.mark.django_db
def test_request_active_user_sends_mail(
    mailoutbox: list,
    django_capture_on_commit_callbacks: _Capture,
) -> None:
    user = UserFactory(email="alice@example.be", is_active=True)
    OrganizationMembershipFactory(user=user, role=Role.ADMIN)

    with django_capture_on_commit_callbacks(execute=True):
        response = Client().post(
            reverse("core:password_reset_request"),
            {"email": "alice@example.be"},
        )

    assert response.status_code == 200
    assert "auth/password_reset_sent.html" in [
        t.name for t in response.templates
    ]
    assert len(mailoutbox) == 1
    msg = mailoutbox[0]
    assert msg.to == ["alice@example.be"]
    # Body contains a usable reset_url whose path resolves to the confirm view.
    match = re.search(r"https?://\S+/password/reset/(\S+)/", msg.body)
    assert match is not None
    token = match.group(1)
    # Resolve the URL: this proves the route name + path shape are wired.
    expected_path = reverse("core:password_reset_confirm", args=[token])
    assert expected_path in msg.body


@pytest.mark.django_db
def test_request_unknown_email_renders_sent_no_mail(
    mailoutbox: list,
) -> None:
    response = Client().post(
        reverse("core:password_reset_request"),
        {"email": "nobody@example.be"},
    )

    assert response.status_code == 200
    assert "auth/password_reset_sent.html" in [
        t.name for t in response.templates
    ]
    assert mailoutbox == []


@pytest.mark.django_db
def test_request_inactive_user_renders_sent_no_mail(
    mailoutbox: list,
) -> None:
    user = UserFactory(email="bob@example.be", is_active=False)
    OrganizationMembershipFactory(user=user, role=Role.ADMIN)

    response = Client().post(
        reverse("core:password_reset_request"),
        {"email": "bob@example.be"},
    )

    assert response.status_code == 200
    assert "auth/password_reset_sent.html" in [
        t.name for t in response.templates
    ]
    assert mailoutbox == []


@pytest.mark.django_db
def test_request_email_normalised_case_insensitive(
    mailoutbox: list,
    django_capture_on_commit_callbacks: _Capture,
) -> None:
    user = UserFactory(email="alice@example.be", is_active=True)
    OrganizationMembershipFactory(user=user, role=Role.ADMIN)

    with django_capture_on_commit_callbacks(execute=True):
        response = Client().post(
            reverse("core:password_reset_request"),
            {"email": "  ALICE@example.be  "},
        )

    assert response.status_code == 200
    assert len(mailoutbox) == 1


# ---------------------------------------------------------------------------
# Confirm flow (issue #59)
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_confirm_get_with_valid_token_renders_form() -> None:
    user = UserFactory(is_active=True)
    OrganizationMembershipFactory(user=user, role=Role.ADMIN)
    token = make_password_reset_token(user)

    response = Client().get(
        reverse("core:password_reset_confirm", args=[token])
    )

    assert response.status_code == 200
    assert "auth/password_reset_confirm.html" in [
        t.name for t in response.templates
    ]


@pytest.mark.django_db
def test_confirm_valid_post_updates_password_and_logs_in() -> None:
    user = UserFactory(is_active=True)
    org = OrganizationFactory(slug="frituur-janssens")
    OrganizationMembershipFactory(user=user, organization=org, role=Role.ADMIN)
    token = make_password_reset_token(user)
    client = Client()

    response = client.post(
        reverse("core:password_reset_confirm", args=[token]),
        {
            "new_password": "n3w-l0ng-p4ssword!",
            "confirm_password": "n3w-l0ng-p4ssword!",
        },
    )

    assert response.status_code == 302
    assert response["Location"] == "/o/frituur-janssens/"
    user.refresh_from_db()
    assert user.check_password("n3w-l0ng-p4ssword!")
    auth_user = get_user(client)
    assert auth_user.is_authenticated
    assert auth_user.pk == user.pk


@pytest.mark.django_db
def test_confirm_mismatched_passwords_keep_old_password() -> None:
    user = UserFactory(is_active=True)
    OrganizationMembershipFactory(user=user, role=Role.ADMIN)
    token = make_password_reset_token(user)

    response = Client().post(
        reverse("core:password_reset_confirm", args=[token]),
        {
            "new_password": "n3w-l0ng-p4ssword!",
            "confirm_password": "different-l0ng-p4ssword!",
        },
    )

    assert response.status_code == 200
    assert "auth/password_reset_confirm.html" in [
        t.name for t in response.templates
    ]
    form = response.context["form"]
    assert "confirm_password" in form.errors
    user.refresh_from_db()
    # Default factory password "password" is unchanged.
    assert user.check_password("password")


@pytest.mark.django_db
def test_confirm_weak_password_keeps_old_password() -> None:
    user = UserFactory(is_active=True)
    OrganizationMembershipFactory(user=user, role=Role.ADMIN)
    token = make_password_reset_token(user)

    response = Client().post(
        reverse("core:password_reset_confirm", args=[token]),
        {"new_password": "12345", "confirm_password": "12345"},
    )

    assert response.status_code == 200
    form = response.context["form"]
    assert "new_password" in form.errors
    user.refresh_from_db()
    assert user.check_password("password")


@pytest.mark.django_db
def test_confirm_tampered_token_renders_failed() -> None:
    user = UserFactory(is_active=True)
    OrganizationMembershipFactory(user=user, role=Role.ADMIN)

    response = Client().get(
        reverse("core:password_reset_confirm", args=["not-a-token"])
    )

    assert response.status_code == 200
    assert "auth/password_reset_failed.html" in [
        t.name for t in response.templates
    ]
    user.refresh_from_db()
    assert user.check_password("password")


@pytest.mark.django_db
def test_confirm_expired_token_renders_failed() -> None:
    user = UserFactory(is_active=True)
    OrganizationMembershipFactory(user=user, role=Role.ADMIN)
    token = make_password_reset_token(user)

    with patch(
        "core.views.auth.verify_password_reset_token",
        side_effect=signing.SignatureExpired("expired"),
    ):
        response = Client().get(
            reverse("core:password_reset_confirm", args=[token])
        )

    assert response.status_code == 200
    assert "auth/password_reset_failed.html" in [
        t.name for t in response.templates
    ]


@pytest.mark.django_db
def test_confirm_inactive_user_renders_failed() -> None:
    # Token issued while user was active; user later deactivated.
    user = UserFactory(is_active=True)
    OrganizationMembershipFactory(user=user, role=Role.ADMIN)
    token = make_password_reset_token(user)
    user.is_active = False
    user.save(update_fields=["is_active"])

    response = Client().post(
        reverse("core:password_reset_confirm", args=[token]),
        {
            "new_password": "n3w-l0ng-p4ssword!",
            "confirm_password": "n3w-l0ng-p4ssword!",
        },
    )

    assert response.status_code == 200
    assert "auth/password_reset_failed.html" in [
        t.name for t in response.templates
    ]
    user.refresh_from_db()
    assert user.check_password("password")
    auth_user = get_user(Client())
    assert not auth_user.is_authenticated


@pytest.mark.django_db
def test_confirm_token_invalidated_after_successful_reset() -> None:
    # The token is bound to the user's password hash via a fingerprint in
    # the signed payload. Once the password is rotated the same link must
    # not be reusable to overwrite the password again, even within the
    # 1h signing window. (Codex review #69, P2.)
    user = UserFactory(is_active=True)
    OrganizationMembershipFactory(user=user, role=Role.ADMIN)
    token = make_password_reset_token(user)

    first = Client().post(
        reverse("core:password_reset_confirm", args=[token]),
        {
            "new_password": "n3w-l0ng-p4ssword!",
            "confirm_password": "n3w-l0ng-p4ssword!",
        },
    )
    assert first.status_code == 302

    # Replay the same token: the password hash has changed so the
    # fingerprint no longer matches.
    replay = Client().post(
        reverse("core:password_reset_confirm", args=[token]),
        {
            "new_password": "h1jacked-p4ssword!",
            "confirm_password": "h1jacked-p4ssword!",
        },
    )
    assert replay.status_code == 200
    assert "auth/password_reset_failed.html" in [
        t.name for t in replay.templates
    ]
    user.refresh_from_db()
    assert user.check_password("n3w-l0ng-p4ssword!")
    assert not user.check_password("h1jacked-p4ssword!")


# ---------------------------------------------------------------------------
# Login page entry-point smoke test
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_login_page_links_to_password_reset() -> None:
    response = Client().get(reverse("core:login"))
    assert response.status_code == 200
    assert reverse("core:password_reset_request") in response.content.decode()
