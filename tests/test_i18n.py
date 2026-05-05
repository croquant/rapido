import pytest
from django.conf import settings
from django.contrib.auth.models import AnonymousUser
from django.test import Client
from django.utils import translation

from core.i18n import resolve_locale
from tests.factories import (
    OrganizationFactory,
    OrganizationMembershipFactory,
    UserFactory,
)


@pytest.mark.django_db
def test_user_preference_wins_over_org_default() -> None:
    user = UserFactory(preferred_language="fr-BE")
    org = OrganizationFactory(default_language="nl-BE")
    assert resolve_locale(user, org) == "fr-BE"


@pytest.mark.django_db
def test_org_default_used_when_user_has_no_preference() -> None:
    user = UserFactory(preferred_language="")
    org = OrganizationFactory(default_language="nl-BE")
    assert resolve_locale(user, org) == "nl-BE"


@pytest.mark.django_db
def test_org_default_used_when_user_is_none() -> None:
    org = OrganizationFactory(default_language="nl-BE")
    assert resolve_locale(None, org) == "nl-BE"


def test_falls_back_to_system_default_when_no_user_or_org() -> None:
    assert resolve_locale(None, None) == settings.LANGUAGE_CODE


def test_anonymous_user_skipped_uses_org_default() -> None:
    org = OrganizationFactory.build(default_language="fr-BE")
    assert resolve_locale(AnonymousUser(), org) == "fr-BE"


def test_anonymous_user_no_org_falls_back_to_system_default() -> None:
    assert resolve_locale(AnonymousUser(), None) == settings.LANGUAGE_CODE


def test_resolve_locale_returns_default_when_no_preference() -> None:
    assert resolve_locale(None, None, default=None) is None


def test_locale_middleware_honors_accept_language() -> None:
    client = Client()
    response = client.get("/", HTTP_ACCEPT_LANGUAGE="fr-BE")
    assert response["Content-Language"].lower().startswith("fr")


@pytest.mark.django_db
def test_authenticated_user_preferred_language_activates_on_request() -> None:
    user = UserFactory(preferred_language="fr-BE", password="pw12345!")
    client = Client()
    assert client.login(email=user.email, password="pw12345!")
    response = client.get("/me/")
    assert response.status_code == 200
    assert response["Content-Language"].lower().startswith("fr")
    assert "modifier le mot de passe" in response.content.decode().lower()


@pytest.mark.django_db
def test_org_default_language_activates_on_org_pages() -> None:
    membership = OrganizationMembershipFactory(
        user__preferred_language="",
        user__password="pw12345!",
        organization__default_language="nl-BE",
    )
    client = Client()
    assert client.login(email=membership.user.email, password="pw12345!")
    response = client.get(f"/o/{membership.organization.slug}/")
    assert response.status_code == 200
    assert response["Content-Language"].lower().startswith("nl")


@pytest.mark.django_db
def test_user_without_preference_falls_back_to_accept_language() -> None:
    user = UserFactory(preferred_language="", password="pw12345!")
    client = Client()
    assert client.login(email=user.email, password="pw12345!")
    response = client.get("/me/", HTTP_ACCEPT_LANGUAGE="fr-BE")
    assert response.status_code == 200
    assert response["Content-Language"].lower().startswith("fr")


@pytest.mark.parametrize(
    "lang,source,expected",
    [
        ("nl-BE", "organization", "organisatie"),
        ("fr-BE", "organization", "organisation"),
        ("de-DE", "organization", "Organisation"),
        ("nl-BE", "preferred language", "voorkeurstaal"),
        ("fr-BE", "preferred language", "langue préférée"),
        ("de-DE", "preferred language", "bevorzugte Sprache"),
    ],
)
def test_translations_compiled(lang: str, source: str, expected: str) -> None:
    with translation.override(lang):
        assert translation.gettext(source) == expected
