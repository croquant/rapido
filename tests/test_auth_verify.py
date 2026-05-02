from unittest.mock import patch

import pytest
from django.contrib.auth import get_user
from django.core import signing
from django.test import Client
from django.urls import reverse

from core.models import Role
from core.services.tokens import VERIFY_SALT, make_token
from tests.factories import (
    OrganizationFactory,
    OrganizationMembershipFactory,
    UserFactory,
)


@pytest.mark.django_db
def test_valid_token_activates_logs_in_and_redirects() -> None:
    user = UserFactory(is_active=False)
    org = OrganizationFactory(is_active=False, slug="frituur-janssens")
    OrganizationMembershipFactory(user=user, organization=org, role=Role.ADMIN)
    token = make_token(user, salt=VERIFY_SALT)
    client = Client()

    response = client.get(reverse("core:verify", args=[token]))

    assert response.status_code == 302
    assert response["Location"] == "/o/frituur-janssens/"
    user.refresh_from_db()
    org.refresh_from_db()
    assert user.is_active is True
    assert org.is_active is True
    auth_user = get_user(client)
    assert auth_user.is_authenticated
    assert auth_user.pk == user.pk


@pytest.mark.django_db
def test_tampered_token_renders_failed_no_state_change() -> None:
    user = UserFactory(is_active=False)
    org = OrganizationFactory(is_active=False)
    OrganizationMembershipFactory(user=user, organization=org, role=Role.ADMIN)
    client = Client()

    response = client.get(reverse("core:verify", args=["not-a-token"]))

    assert response.status_code == 200
    assert "auth/verify_failed.html" in [t.name for t in response.templates]
    user.refresh_from_db()
    org.refresh_from_db()
    assert user.is_active is False
    assert org.is_active is False
    auth_user = get_user(client)
    assert not auth_user.is_authenticated


@pytest.mark.django_db
def test_expired_token_renders_failed() -> None:
    user = UserFactory(is_active=False)
    org = OrganizationFactory(is_active=False)
    OrganizationMembershipFactory(user=user, organization=org, role=Role.ADMIN)
    token = make_token(user, salt=VERIFY_SALT)
    client = Client()

    with patch(
        "core.services.activation.verify_token",
        side_effect=signing.SignatureExpired("expired"),
    ):
        response = client.get(reverse("core:verify", args=[token]))

    assert response.status_code == 200
    assert "auth/verify_failed.html" in [t.name for t in response.templates]
    user.refresh_from_db()
    assert user.is_active is False


@pytest.mark.django_db
def test_second_click_renders_already() -> None:
    user = UserFactory(is_active=False)
    org = OrganizationFactory(is_active=False)
    OrganizationMembershipFactory(user=user, organization=org, role=Role.ADMIN)
    token = make_token(user, salt=VERIFY_SALT)
    client = Client()

    first = client.get(reverse("core:verify", args=[token]))
    assert first.status_code == 302

    # Fresh client so the active session doesn't influence the second click.
    second_client = Client()
    second = second_client.get(reverse("core:verify", args=[token]))

    assert second.status_code == 200
    assert "auth/verify_already.html" in [t.name for t in second.templates]


@pytest.mark.django_db
def test_no_active_admin_membership_renders_failed() -> None:
    user = UserFactory(is_active=False)
    org = OrganizationFactory(is_active=False)
    OrganizationMembershipFactory(
        user=user, organization=org, role=Role.OPERATOR
    )
    token = make_token(user, salt=VERIFY_SALT)
    client = Client()

    response = client.get(reverse("core:verify", args=[token]))

    assert response.status_code == 200
    assert "auth/verify_failed.html" in [t.name for t in response.templates]
    user.refresh_from_db()
    assert user.is_active is False


@pytest.mark.django_db
def test_authenticated_other_user_session_swaps_to_activated_user() -> None:
    other = UserFactory()
    user = UserFactory(is_active=False)
    org = OrganizationFactory(is_active=False, slug="acme")
    OrganizationMembershipFactory(user=user, organization=org, role=Role.ADMIN)
    token = make_token(user, salt=VERIFY_SALT)
    client = Client()
    client.force_login(other)

    response = client.get(reverse("core:verify", args=[token]))

    assert response.status_code == 302
    assert response["Location"] == "/o/acme/"
    user.refresh_from_db()
    assert user.is_active is True
    auth_user = get_user(client)
    assert auth_user.is_authenticated
    assert auth_user.pk == user.pk
