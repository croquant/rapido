from typing import Any
from unittest.mock import patch

import pytest
from django.conf import settings
from django.test import Client
from django.urls import reverse

from core.models import Organization, OrganizationMembership, Role, User
from tests.factories import OrganizationFactory, UserFactory

_Capture = Any


def _payload(**overrides: str) -> dict[str, str]:
    base = {
        "email": "owner@example.be",
        "password": "Sup3rSecretPass!",
        "org_name": "Frituur Janssens",
        "org_slug": "frituur-janssens",
        "vat_number": "BE0417710407",
        "country": "BE",
        "default_language": "en-US",
    }
    base.update(overrides)
    return base


@pytest.mark.django_db
def test_get_renders_200() -> None:
    client = Client()
    response = client.get(reverse("core:signup"))
    assert response.status_code == 200


@pytest.mark.django_db
def test_get_preselects_default_language_from_accept_language() -> None:
    client = Client()
    response = client.get(reverse("core:signup"), HTTP_ACCEPT_LANGUAGE="nl-BE")
    assert response.status_code == 200
    form = response.context["form"]
    assert form.initial["default_language"] == "nl-BE"


@pytest.mark.django_db
def test_get_default_language_falls_back_when_unsupported() -> None:
    client = Client()
    response = client.get(reverse("core:signup"), HTTP_ACCEPT_LANGUAGE="ja")
    assert response.status_code == 200
    form = response.context["form"]
    assert form.initial["default_language"] == settings.LANGUAGE_CODE


@pytest.mark.django_db
def test_post_valid_redirects_to_done_and_creates_rows(
    django_capture_on_commit_callbacks: _Capture,
) -> None:
    client = Client()
    with django_capture_on_commit_callbacks(execute=False):
        response = client.post(reverse("core:signup"), data=_payload())
    assert response.status_code == 302
    assert response["Location"] == reverse("core:signup_done")
    assert Organization.objects.count() == 1
    assert User.objects.count() == 1
    assert OrganizationMembership.objects.count() == 1
    org = Organization.objects.get()
    user = User.objects.get()
    mem = OrganizationMembership.objects.get()
    assert org.is_active is False
    assert user.is_active is False
    assert mem.is_active is True
    assert mem.role == Role.ADMIN
    assert org.default_language == "en-US"
    assert user.preferred_language == "en-US"
    assert org.billing_email == "owner@example.be"


@pytest.mark.django_db
def test_post_invalid_vat_returns_field_error() -> None:
    client = Client()
    response = client.post(
        reverse("core:signup"),
        data=_payload(vat_number="FR12345678901"),
    )
    assert response.status_code == 200
    form = response.context["form"]
    assert "vat_number" in form.errors
    assert Organization.objects.count() == 0
    assert User.objects.count() == 0


@pytest.mark.django_db
def test_post_invalid_slug_returns_field_error() -> None:
    client = Client()
    response = client.post(
        reverse("core:signup"),
        data=_payload(org_slug="Not A Slug!"),
    )
    assert response.status_code == 200
    form = response.context["form"]
    assert "org_slug" in form.errors
    assert Organization.objects.count() == 0


@pytest.mark.django_db
def test_post_duplicate_slug_returns_form_error_not_500() -> None:
    OrganizationFactory(slug="frituur-janssens")
    client = Client()
    response = client.post(reverse("core:signup"), data=_payload())
    assert response.status_code == 200
    form = response.context["form"]
    assert "org_slug" in form.errors


@pytest.mark.django_db
def test_post_duplicate_email_returns_form_error_not_500() -> None:
    UserFactory(email="owner@example.be")
    client = Client()
    response = client.post(
        reverse("core:signup"), data=_payload(email="OWNER@example.be")
    )
    assert response.status_code == 200
    form = response.context["form"]
    assert "email" in form.errors


@pytest.mark.django_db
def test_post_weak_password_returns_field_error() -> None:
    client = Client()
    response = client.post(
        reverse("core:signup"), data=_payload(password="123")
    )
    assert response.status_code == 200
    form = response.context["form"]
    assert "password" in form.errors
    assert Organization.objects.count() == 0


@pytest.mark.django_db
def test_post_valid_enqueues_verify_email_on_commit(
    django_capture_on_commit_callbacks: _Capture,
) -> None:
    client = Client()
    with patch("core.services.signup.send_templated") as send:
        with django_capture_on_commit_callbacks(execute=True) as callbacks:
            response = client.post(
                reverse("core:signup"),
                data=_payload(default_language="nl-BE"),
            )
        assert response.status_code == 302
        assert len(callbacks) == 1
        send.assert_called_once()
        args, kwargs = send.call_args
        assert args == ("email/verify",)
        assert kwargs["to"].email == "owner@example.be"
        assert kwargs["language"] == "nl-BE"


@pytest.mark.django_db
def test_authenticated_user_is_redirected() -> None:
    user = UserFactory()
    client = Client()
    client.force_login(user)
    response = client.get(reverse("core:signup"))
    assert response.status_code == 302
    assert response["Location"] == settings.LOGIN_REDIRECT_URL


@pytest.mark.django_db
def test_signup_done_renders_200() -> None:
    client = Client()
    response = client.get(reverse("core:signup_done"))
    assert response.status_code == 200


@pytest.mark.django_db
def test_email_normalized_to_lowercase() -> None:
    client = Client()
    response = client.post(
        reverse("core:signup"), data=_payload(email="OWNER@Example.BE")
    )
    assert response.status_code == 302
    user = User.objects.get()
    assert user.email == "owner@example.be"
