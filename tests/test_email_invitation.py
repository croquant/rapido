from datetime import timedelta
from types import SimpleNamespace
from typing import Any

import pytest
from django.conf import settings
from django.utils import timezone

from core.models import User
from core.services.mail import send_templated


def _user(email: str = "invitee@example.be", lang: str = "en-us") -> User:
    return User(email=email, preferred_language=lang)


def _ctx(overrides: dict[str, Any] | None = None) -> dict[str, Any]:
    base: dict[str, Any] = {
        "invitee_email": "invitee@example.be",
        "inviter_name": "Alice Admin",
        "organization_name": "Cafe Test",
        "role": "OPERATOR",
        "locations": [SimpleNamespace(name="Main")],
        "accept_url": "https://example.test/invite/abc/",
        "expires_at": timezone.now() + timedelta(days=7),
    }
    if overrides:
        base.update(overrides)
    return base


@pytest.mark.django_db
def test_invitation_renders_text_and_html(mailoutbox: list) -> None:
    send_templated("email/invitation", to=_user(), context=_ctx())
    msg = mailoutbox[0]
    assert msg.subject
    assert msg.body
    assert len(msg.alternatives) == 1
    html, mime = msg.alternatives[0]
    assert mime == "text/html"
    assert str(html)


@pytest.mark.django_db
def test_invitation_html_has_accept_anchor(mailoutbox: list) -> None:
    ctx = _ctx()
    send_templated("email/invitation", to=_user(), context=ctx)
    html = str(mailoutbox[0].alternatives[0][0])
    assert f'href="{ctx["accept_url"]}"' in html


@pytest.mark.django_db
def test_invitation_brand_appears_in_body(mailoutbox: list) -> None:
    send_templated("email/invitation", to=_user(), context=_ctx())
    msg = mailoutbox[0]
    assert settings.SITE_BRAND in msg.body
    assert settings.SITE_BRAND in str(msg.alternatives[0][0])


@pytest.mark.django_db
@pytest.mark.parametrize("language", ["en-us", "nl-BE", "fr-BE"])
def test_invitation_renders_in_each_language(
    mailoutbox: list, language: str
) -> None:
    ctx = _ctx()
    send_templated("email/invitation", to=_user(lang=language), context=ctx)
    msg = mailoutbox[-1]
    html = str(msg.alternatives[0][0])
    assert msg.subject
    assert ctx["accept_url"] in msg.body
    assert ctx["accept_url"] in html
    assert f'lang="{language.lower()}"' in html.lower()


@pytest.mark.django_db
def test_invitation_subject_is_single_line(mailoutbox: list) -> None:
    send_templated("email/invitation", to=_user(), context=_ctx())
    subject = mailoutbox[0].subject
    assert "\n" not in subject
    assert "\r" not in subject


@pytest.mark.django_db
def test_invitation_admin_omits_locations_section(mailoutbox: list) -> None:
    send_templated(
        "email/invitation",
        to=_user(),
        context=_ctx({"role": "ADMIN", "locations": []}),
    )
    msg = mailoutbox[0]
    html = str(msg.alternatives[0][0])
    assert "Your assigned locations" not in msg.body
    assert "Your assigned locations" not in html


@pytest.mark.django_db
def test_invitation_operator_lists_location_names(mailoutbox: list) -> None:
    locations = [
        SimpleNamespace(name="Brussels"),
        SimpleNamespace(name="Ghent"),
    ]
    send_templated(
        "email/invitation",
        to=_user(),
        context=_ctx({"role": "OPERATOR", "locations": locations}),
    )
    msg = mailoutbox[0]
    html = str(msg.alternatives[0][0])
    assert "Brussels" in msg.body
    assert "Ghent" in msg.body
    assert "Brussels" in html
    assert "Ghent" in html


@pytest.mark.django_db
def test_invitation_revoked_renders(mailoutbox: list) -> None:
    send_templated(
        "email/invitation_revoked",
        to=_user(),
        context={
            "invitee_email": "invitee@example.be",
            "organization_name": "Cafe Test",
        },
    )
    msg = mailoutbox[0]
    assert msg.subject
    assert msg.body
    html = str(msg.alternatives[0][0])
    assert "https://example.test/invite/" not in msg.body
    assert "https://example.test/invite/" not in html
    assert "Cafe Test" in msg.body
