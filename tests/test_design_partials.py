import pytest
from django.conf import settings
from django.contrib.auth.models import AbstractBaseUser, AnonymousUser
from django.contrib.messages import constants as message_levels
from django.contrib.messages.storage.base import Message
from django.http import HttpRequest, HttpResponse
from django.template import Context, RequestContext, Template
from django.test import RequestFactory, override_settings
from django.urls import include, path

from core.models import Organization
from tests.factories import OrganizationFactory, UserFactory


def _stub(request: HttpRequest) -> HttpResponse:
    del request
    return HttpResponse()


_core_patterns = (
    [
        path("logout/", _stub, name="logout"),
        path("me/", _stub, name="profile"),
    ],
    "core",
)

urlpatterns = [
    path("", include(_core_patterns, namespace="core")),
    path("i18n/", include("django.conf.urls.i18n")),
]


def _request(
    path: str = "/",
    user: AbstractBaseUser | AnonymousUser | None = None,
    organization: Organization | None = None,
) -> HttpRequest:
    rf = RequestFactory()
    req = rf.get(path)
    req.user = user if user is not None else AnonymousUser()  # type: ignore[assignment]
    req.organization = organization  # type: ignore[attr-defined]
    return req


def _render_include(
    template_path: str,
    request: HttpRequest | None = None,
    **ctx: object,
) -> str:
    tpl = Template('{% include "' + template_path + '" %}')
    if request is not None:
        return tpl.render(RequestContext(request, ctx))
    return tpl.render(Context(ctx))


# ---------- nav_top ----------


def test_nav_top_anonymous_renders_brand_only() -> None:
    out = _render_include("_partials/nav_top.html", request=_request())
    assert ">rapido<" in out
    # Anonymous users see no user menu (gated to is_authenticated), and the
    # language switcher now lives inside the user menu, so the setlang form
    # is not present in the anonymous render.
    assert "/i18n/setlang/" not in out


@pytest.mark.django_db
def test_nav_top_shows_org_name_when_org_in_context() -> None:
    org = OrganizationFactory(name="Frituur Centrale")
    user = UserFactory()
    out = _render_include(
        "_partials/nav_top.html",
        request=_request(user=user, organization=org),
    )
    assert "Frituur Centrale" in out


@pytest.mark.django_db
def test_nav_top_omits_org_name_without_org_context() -> None:
    user = UserFactory()
    out = _render_include("_partials/nav_top.html", request=_request(user=user))
    assert "<li>" in out
    assert "Frituur" not in out


# ---------- user_menu ----------


def test_user_menu_silent_for_anonymous() -> None:
    out = _render_include(
        "_partials/user_menu.html", request=_request(user=AnonymousUser())
    )
    assert "<details" not in out
    assert "Profile" not in out
    assert "Sign out" not in out


@pytest.mark.django_db
def test_user_menu_shows_full_name_when_set() -> None:
    user = UserFactory(first_name="Alice", last_name="Brown")
    out = _render_include(
        "_partials/user_menu.html", request=_request(user=user)
    )
    assert "Alice Brown" in out


@pytest.mark.django_db
def test_user_menu_falls_back_to_email_when_name_blank() -> None:
    user = UserFactory(first_name="", last_name="", email="alice@example.be")
    out = _render_include(
        "_partials/user_menu.html", request=_request(user=user)
    )
    assert "alice@example.be" in out


@pytest.mark.django_db
@override_settings(ROOT_URLCONF=__name__)
def test_user_menu_renders_profile_and_logout() -> None:
    user = UserFactory()
    out = _render_include(
        "_partials/user_menu.html", request=_request(user=user)
    )
    assert 'href="/me/"' in out
    assert "Profile" in out
    assert 'action="/logout/"' in out
    assert 'method="post"' in out
    assert "Sign out" in out
    assert "csrfmiddlewaretoken" in out


# ---------- lang_switcher ----------


def test_lang_switcher_visible_for_anonymous() -> None:
    out = _render_include(
        "_partials/lang_switcher.html",
        request=_request(user=AnonymousUser()),
    )
    assert "<form" in out
    assert 'action="/i18n/setlang/"' in out


@pytest.mark.django_db
def test_lang_switcher_hidden_for_user_with_preferred_language() -> None:
    user = UserFactory(preferred_language="nl-BE")
    out = _render_include(
        "_partials/lang_switcher.html", request=_request(user=user)
    )
    assert out.strip() == ""


@pytest.mark.django_db
def test_lang_switcher_visible_for_user_with_empty_preferred_language() -> None:
    user = UserFactory(preferred_language="")
    out = _render_include(
        "_partials/lang_switcher.html", request=_request(user=user)
    )
    assert "<form" in out


def test_lang_switcher_next_field_equals_request_path() -> None:
    out = _render_include(
        "_partials/lang_switcher.html",
        request=_request(path="/o/acme/dashboard/", user=AnonymousUser()),
    )
    assert 'name="next"' in out
    assert 'value="/o/acme/dashboard/"' in out


def test_lang_switcher_next_field_preserves_query_string() -> None:
    out = _render_include(
        "_partials/lang_switcher.html",
        request=_request(
            path="/o/acme/orders/?status=paid&page=2",
            user=AnonymousUser(),
        ),
    )
    assert 'value="/o/acme/orders/?status=paid&amp;page=2"' in out


def test_lang_switcher_lists_all_supported_languages() -> None:
    out = _render_include(
        "_partials/lang_switcher.html",
        request=_request(user=AnonymousUser()),
    )
    for code, _ in settings.LANGUAGES:
        assert f'value="{code}"' in out


def test_lang_switcher_includes_csrf_token() -> None:
    out = _render_include(
        "_partials/lang_switcher.html",
        request=_request(user=AnonymousUser()),
    )
    assert "csrfmiddlewaretoken" in out


# ---------- flash ----------


def _msg(level: int, content: str, extra_tags: str = "") -> Message:
    return Message(level=level, message=content, extra_tags=extra_tags)


def test_flash_wrapper_id_present_when_no_messages() -> None:
    out = _render_include("_partials/flash.html")
    assert 'id="flash"' in out
    assert "<article" not in out


def test_flash_renders_one_article_per_message() -> None:
    msgs = [
        _msg(message_levels.INFO, "Hi"),
        _msg(message_levels.SUCCESS, "OK"),
    ]
    out = _render_include("_partials/flash.html", messages=msgs)
    assert out.count("<article") == 2
    assert "Hi" in out
    assert "OK" in out


def test_flash_uses_alert_role_for_warning_and_error() -> None:
    msgs = [
        _msg(message_levels.WARNING, "warn"),
        _msg(message_levels.ERROR, "err"),
    ]
    out = _render_include("_partials/flash.html", messages=msgs)
    assert out.count('role="alert"') == 2


def test_flash_uses_status_role_for_info_and_success() -> None:
    msgs = [
        _msg(message_levels.INFO, "i"),
        _msg(message_levels.SUCCESS, "s"),
    ]
    out = _render_include("_partials/flash.html", messages=msgs)
    assert out.count('role="status"') == 2


def test_flash_includes_message_tag_class() -> None:
    msgs = [_msg(message_levels.SUCCESS, "ok")]
    out = _render_include("_partials/flash.html", messages=msgs)
    assert "message-success" in out


# ---------- modal ----------


def test_modal_uses_native_dialog() -> None:
    out = _render_include("_partials/modal.html")
    assert "<dialog" in out
    assert 'id="modal"' in out
    assert "</dialog>" in out


def test_modal_body_block_is_overridable() -> None:
    tpl = Template(
        '{% extends "_partials/modal.html" %}'
        "{% block modal_body %}<p>hello inside.</p>{% endblock %}"
    )
    out = tpl.render(Context({}))
    assert "<p>hello inside.</p>" in out


# ---------- _base.html modal listeners ----------


def test_base_html_includes_modal_open_and_close_listeners() -> None:
    out = Template('{% extends "base_public.html" %}').render(
        RequestContext(_request())
    )
    assert "modal:open" in out
    assert "modal:close" in out
    assert "showModal()" in out
