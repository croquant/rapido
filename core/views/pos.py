from django.http import Http404, HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, render

from core.decorators import permission_required
from core.models import (
    Location,
    LocationMembership,
    OrganizationMembership,
    Role,
)


@permission_required()
def pos_org(request: HttpRequest, slug: str) -> HttpResponse:  # noqa: ARG001
    return render(
        request,
        "pos/coming_soon.html",
        {
            "organization": request.organization,  # type: ignore[attr-defined]
            "location": None,
        },
    )


@permission_required()
def pos_location(
    request: HttpRequest,
    slug: str,  # noqa: ARG001
    lslug: str,
) -> HttpResponse:
    location = get_object_or_404(
        Location.tenant_objects.for_request(request),
        slug=lslug,
        is_active=True,
    )
    user = request.user
    if not user.is_superuser:
        membership = (
            OrganizationMembership.tenant_objects.for_request(request)
            .filter(user=user, is_active=True)
            .first()
        )
        if membership and membership.role == Role.OPERATOR:
            has_location = (
                LocationMembership.tenant_objects.for_request(request)
                .filter(user=user, location=location, is_active=True)
                .exists()
            )
            if not has_location:
                raise Http404
    return render(
        request,
        "pos/coming_soon.html",
        {
            "organization": request.organization,  # type: ignore[attr-defined]
            "location": location,
        },
    )
