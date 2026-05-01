import re
from collections.abc import Callable

from django.http import Http404, HttpRequest, HttpResponse

from core.models import Organization

_TENANT_PATH_RE = re.compile(r"^/o/(?P<slug>[a-z0-9-]+)/")


class TenantMiddleware:
    def __init__(
        self,
        get_response: Callable[[HttpRequest], HttpResponse],
    ) -> None:
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        request.organization = None  # type: ignore[attr-defined]
        match = _TENANT_PATH_RE.match(request.path)
        if match is None:
            return self.get_response(request)

        slug = match["slug"]
        user = request.user

        if user.is_authenticated and user.is_superuser:
            org = Organization.objects.filter(slug=slug, is_active=True).first()
        elif user.is_authenticated:
            org = Organization.objects.filter(
                slug=slug,
                is_active=True,
                organization_memberships__user=user,
                organization_memberships__is_active=True,
            ).first()
        else:
            org = None

        if org is None:
            raise Http404

        request.organization = org  # type: ignore[attr-defined]
        return self.get_response(request)
