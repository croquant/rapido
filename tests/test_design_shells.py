import pytest
from django.contrib.auth.models import AnonymousUser
from django.http import HttpRequest
from django.template.loader import render_to_string
from django.test import RequestFactory

SHELLS = ["base_public.html", "base_picker.html", "base_org.html"]


def _req() -> HttpRequest:
    rf = RequestFactory()
    r = rf.get("/")
    r.user = AnonymousUser()  # type: ignore[assignment]
    r.organization = None  # type: ignore[attr-defined]
    return r


@pytest.mark.parametrize("shell", SHELLS)
def test_shell_has_lang_en_us(shell: str) -> None:
    out = render_to_string(shell, {}, request=_req())
    assert 'lang="en-us"' in out.lower()


@pytest.mark.parametrize("shell", SHELLS)
def test_shell_has_single_main(shell: str) -> None:
    out = render_to_string(shell, {}, request=_req())
    assert out.count("<main") == 1
    assert out.count('id="main"') == 1


@pytest.mark.parametrize("shell", SHELLS)
def test_shell_has_skip_link(shell: str) -> None:
    out = render_to_string(shell, {}, request=_req())
    assert 'class="skip-link"' in out
    assert 'href="#main"' in out


@pytest.mark.parametrize("shell", SHELLS)
def test_shell_stylesheet_order(shell: str) -> None:
    out = render_to_string(shell, {}, request=_req())
    pico = out.find("pico.min.css")
    brand = out.find("brand.css")
    assert pico != -1
    assert brand != -1
    assert pico < brand


def test_org_shell_has_rail() -> None:
    out = render_to_string("base_org.html", {}, request=_req())
    assert 'class="rail"' in out
