import pytest
from django.contrib.auth.models import AnonymousUser
from django.http import Http404, HttpRequest, HttpResponse
from django.test import RequestFactory

from core.decorators import permission_required
from core.models import Organization, Role
from tests.factories import (
    OrganizationFactory,
    OrganizationMembershipFactory,
    UserFactory,
)


def _view(_request: HttpRequest) -> HttpResponse:
    return HttpResponse("ok")


def _request(
    user: object,
    organization: Organization | None,
    *,
    path: str = "/o/acme/settings/",
) -> HttpRequest:
    req = RequestFactory().get(path)
    req.user = user  # type: ignore[assignment]
    req.organization = organization  # type: ignore[attr-defined]
    return req


# ---- anonymous --------------------------------------------------------------


def test_anonymous_redirects_to_login() -> None:
    view = permission_required()(_view)
    req = _request(AnonymousUser(), None, path="/o/acme/settings/")
    response = view(req)
    assert response.status_code == 302
    assert response["Location"].startswith("/login/")
    assert "next=/o/acme/settings/" in response["Location"]


# ---- missing organization ---------------------------------------------------


@pytest.mark.django_db
def test_missing_organization_returns_404() -> None:
    view = permission_required()(_view)
    user = UserFactory()
    with pytest.raises(Http404):
        view(_request(user, None))


@pytest.mark.django_db
def test_superuser_without_organization_still_404() -> None:
    view = permission_required(Role.ADMIN)(_view)
    user = UserFactory(superuser=True)
    with pytest.raises(Http404):
        view(_request(user, None))


# ---- membership checks ------------------------------------------------------


@pytest.mark.django_db
def test_authenticated_non_member_returns_403() -> None:
    view = permission_required()(_view)
    user = UserFactory()
    org = OrganizationFactory()
    response = view(_request(user, org))
    assert response.status_code == 403


@pytest.mark.django_db
def test_inactive_membership_returns_403() -> None:
    view = permission_required()(_view)
    membership = OrganizationMembershipFactory(is_active=False)
    response = view(_request(membership.user, membership.organization))
    assert response.status_code == 403


@pytest.mark.django_db
def test_active_member_no_role_required_passes() -> None:
    view = permission_required()(_view)
    membership = OrganizationMembershipFactory(role=Role.OPERATOR)
    response = view(_request(membership.user, membership.organization))
    assert response.status_code == 200


# ---- role checks ------------------------------------------------------------


@pytest.mark.django_db
def test_operator_blocked_from_admin_view() -> None:
    view = permission_required(Role.ADMIN)(_view)
    membership = OrganizationMembershipFactory(role=Role.OPERATOR)
    response = view(_request(membership.user, membership.organization))
    assert response.status_code == 403


@pytest.mark.django_db
def test_admin_passes_admin_view() -> None:
    view = permission_required(Role.ADMIN)(_view)
    membership = OrganizationMembershipFactory(role=Role.ADMIN)
    response = view(_request(membership.user, membership.organization))
    assert response.status_code == 200


@pytest.mark.django_db
def test_operator_passes_operator_view() -> None:
    view = permission_required(Role.OPERATOR)(_view)
    membership = OrganizationMembershipFactory(role=Role.OPERATOR)
    response = view(_request(membership.user, membership.organization))
    assert response.status_code == 200


# ---- superuser bypass -------------------------------------------------------


@pytest.mark.django_db
def test_superuser_bypasses_membership_and_role() -> None:
    view = permission_required(Role.ADMIN)(_view)
    user = UserFactory(superuser=True)
    org = OrganizationFactory()
    response = view(_request(user, org))
    assert response.status_code == 200


# ---- composability ----------------------------------------------------------


def test_wraps_preserves_view_metadata() -> None:
    view = permission_required(Role.ADMIN)(_view)
    assert view.__name__ == "_view"
    assert view.__wrapped__ is _view  # type: ignore[attr-defined]
