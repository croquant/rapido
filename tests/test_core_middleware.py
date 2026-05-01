import pytest
from django.contrib.auth.models import AnonymousUser
from django.core.handlers.wsgi import WSGIRequest
from django.http import Http404, HttpResponse
from django.test import RequestFactory

from core.middleware import TenantMiddleware
from core.models import User
from tests.factories import (
    OrganizationFactory,
    OrganizationMembershipFactory,
    UserFactory,
)

SENTINEL = HttpResponse("ok")


def _get_response(request: WSGIRequest) -> HttpResponse:
    request._view_called = True  # type: ignore[attr-defined]
    return SENTINEL


def _call(
    path: str, user: User | AnonymousUser
) -> tuple[HttpResponse, WSGIRequest]:
    rf = RequestFactory()
    request = rf.get(path)
    request.user = user
    mw = TenantMiddleware(_get_response)
    response = mw(request)
    return response, request


@pytest.mark.parametrize("path", ["/", "/login/", "/admin/", "/o/", "/o/Foo/"])
def test_non_tenant_paths_pass_through(path: str) -> None:
    response, request = _call(path, AnonymousUser())
    assert response is SENTINEL
    assert request.organization is None
    assert getattr(request, "_view_called", False) is True


@pytest.mark.django_db
def test_anonymous_existing_org_returns_404() -> None:
    org = OrganizationFactory()
    with pytest.raises(Http404):
        _call(f"/o/{org.slug}/", AnonymousUser())


def test_anonymous_missing_org_returns_404() -> None:
    with pytest.raises(Http404):
        _call("/o/does-not-exist/", AnonymousUser())


@pytest.mark.django_db
def test_authed_no_membership_returns_404() -> None:
    org = OrganizationFactory()
    user = UserFactory()
    with pytest.raises(Http404):
        _call(f"/o/{org.slug}/", user)


@pytest.mark.django_db
def test_authed_inactive_membership_returns_404() -> None:
    membership = OrganizationMembershipFactory(is_active=False)
    with pytest.raises(Http404):
        _call(f"/o/{membership.organization.slug}/", membership.user)


@pytest.mark.django_db
def test_authed_membership_on_other_org_returns_404() -> None:
    membership = OrganizationMembershipFactory()
    other = OrganizationFactory()
    with pytest.raises(Http404):
        _call(f"/o/{other.slug}/", membership.user)


@pytest.mark.django_db
def test_authed_active_membership_resolves_org() -> None:
    membership = OrganizationMembershipFactory()
    path = f"/o/{membership.organization.slug}/"
    response, request = _call(path, membership.user)
    assert response is SENTINEL
    assert request.organization == membership.organization


@pytest.mark.django_db
def test_authed_inactive_org_returns_404() -> None:
    membership = OrganizationMembershipFactory(organization__is_active=False)
    with pytest.raises(Http404):
        _call(f"/o/{membership.organization.slug}/", membership.user)


@pytest.mark.django_db
def test_superuser_resolves_existing_org_without_membership() -> None:
    org = OrganizationFactory()
    user = UserFactory(is_superuser=True, is_staff=True)
    response, request = _call(f"/o/{org.slug}/", user)
    assert response is SENTINEL
    assert request.organization == org


@pytest.mark.django_db
def test_superuser_missing_org_returns_404() -> None:
    user = UserFactory(is_superuser=True, is_staff=True)
    with pytest.raises(Http404):
        _call("/o/does-not-exist/", user)


@pytest.mark.django_db
def test_superuser_inactive_org_returns_404() -> None:
    org = OrganizationFactory(is_active=False)
    user = UserFactory(is_superuser=True, is_staff=True)
    with pytest.raises(Http404):
        _call(f"/o/{org.slug}/", user)


@pytest.mark.django_db
def test_nested_path_resolves_org() -> None:
    membership = OrganizationMembershipFactory()
    path = f"/o/{membership.organization.slug}/locations/abc/edit/"
    response, request = _call(path, membership.user)
    assert response is SENTINEL
    assert request.organization == membership.organization
