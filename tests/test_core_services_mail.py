from pathlib import Path

import pytest
from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.test import override_settings

from core.services.mail import send_templated
from tests.factories import UserFactory

FIXTURE_DIR = Path(__file__).parent / "templates"


def _override_template_dirs() -> dict:
    return {
        "TEMPLATES": [
            {
                **settings.TEMPLATES[0],
                "DIRS": [FIXTURE_DIR, *settings.TEMPLATES[0]["DIRS"]],
            }
        ]
    }


@pytest.mark.django_db
def test_uses_recipient_preferred_language(mailoutbox: list) -> None:
    user = UserFactory(preferred_language="nl-BE")
    send_templated(
        "email/verify",
        to=user,
        context={"verify_url": "https://example.com/v/abc"},
    )
    msg = mailoutbox[0]
    html = str(msg.alternatives[0][0]).lower()
    assert 'lang="nl-be"' in html


@pytest.mark.django_db
def test_language_kwarg_overrides_recipient_pref(mailoutbox: list) -> None:
    user = UserFactory(preferred_language="nl-BE")
    send_templated(
        "email/verify",
        to=user,
        language="fr-BE",
        context={"verify_url": "https://example.com/v/abc"},
    )
    html = str(mailoutbox[0].alternatives[0][0]).lower()
    assert 'lang="fr-be"' in html


@pytest.mark.django_db
def test_falls_back_to_system_default_when_no_pref(mailoutbox: list) -> None:
    user = UserFactory(preferred_language="")
    send_templated(
        "email/verify",
        to=user,
        context={"verify_url": "https://example.com/v/abc"},
    )
    html = str(mailoutbox[0].alternatives[0][0]).lower()
    assert f'lang="{settings.LANGUAGE_CODE.lower()}"' in html


@pytest.mark.django_db
@override_settings(**_override_template_dirs())
def test_html_alternative_attached_when_template_exists(
    mailoutbox: list,
) -> None:
    user = UserFactory()
    send_templated("email/_fixture_full", to=user, context={})
    msg = mailoutbox[0]
    assert isinstance(msg, EmailMultiAlternatives)
    assert len(msg.alternatives) == 1
    html, mime = msg.alternatives[0]
    assert mime == "text/html"
    assert "<p>html-body</p>" in str(html)
    assert "text-body" in msg.body


@pytest.mark.django_db
@override_settings(**_override_template_dirs())
def test_html_alternative_absent_when_template_missing(
    mailoutbox: list,
) -> None:
    user = UserFactory()
    send_templated("email/_fixture_text_only", to=user, context={})
    msg = mailoutbox[0]
    assert msg.alternatives == []
    assert "text-only-body" in msg.body


@pytest.mark.django_db
@override_settings(**_override_template_dirs())
def test_subject_is_rendered_and_stripped(mailoutbox: list) -> None:
    user = UserFactory()
    send_templated("email/_fixture_full", to=user, context={})
    assert mailoutbox[0].subject == "fixture-subject"


@pytest.mark.django_db
def test_recipient_address_and_from(mailoutbox: list) -> None:
    user = UserFactory(email="alice@example.be")
    send_templated(
        "email/verify",
        to=user,
        context={"verify_url": "https://example.com/v/abc"},
    )
    msg = mailoutbox[0]
    assert msg.to == ["alice@example.be"]
    assert msg.from_email == settings.DEFAULT_FROM_EMAIL


@pytest.mark.django_db
def test_verify_template_renders(mailoutbox: list) -> None:
    user = UserFactory(email="alice@example.be", first_name="Alice")
    send_templated(
        "email/verify",
        to=user,
        context={
            "verify_url": "https://example.com/v/tok",
            "org_name": "Acme",
        },
    )
    msg = mailoutbox[0]
    html = str(msg.alternatives[0][0])
    assert msg.subject
    assert "https://example.com/v/tok" in msg.body
    assert "https://example.com/v/tok" in html
    assert "Alice" in msg.body
    assert "Acme" in msg.body


@pytest.mark.django_db
def test_password_reset_template_renders(mailoutbox: list) -> None:
    user = UserFactory(email="alice@example.be")
    send_templated(
        "email/password_reset",
        to=user,
        context={"reset_url": "https://example.com/r/tok"},
    )
    msg = mailoutbox[0]
    html = str(msg.alternatives[0][0])
    assert msg.subject
    assert "https://example.com/r/tok" in msg.body
    assert "https://example.com/r/tok" in html


@pytest.mark.django_db
def test_brand_appears_in_body(mailoutbox: list) -> None:
    user = UserFactory()
    send_templated(
        "email/verify",
        to=user,
        context={"verify_url": "https://example.com/v/abc"},
    )
    assert settings.SITE_BRAND in mailoutbox[0].body
