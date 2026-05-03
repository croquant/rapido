from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, render

from core.decorators import permission_required
from core.models import Location


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
        Location,
        organization=request.organization,  # type: ignore[attr-defined]
        slug=lslug,
        is_active=True,
    )
    return render(
        request,
        "pos/coming_soon.html",
        {
            "organization": request.organization,  # type: ignore[attr-defined]
            "location": location,
        },
    )
