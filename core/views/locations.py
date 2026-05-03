from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from core.decorators import permission_required
from core.forms.location import LocationForm
from core.models import (
    Location,
    LocationMembership,
    OrganizationMembership,
    Role,
    User,
)
from core.services import location as location_service
from core.services import membership as membership_service


def _row(request: HttpRequest, location: Location) -> HttpResponse:
    return render(
        request,
        "locations/_row.html",
        {
            "organization": request.organization,  # type: ignore[attr-defined]
            "location": location,
        },
    )


@permission_required(Role.ADMIN)
def list_view(request: HttpRequest, slug: str) -> HttpResponse:  # noqa: ARG001
    locations = Location.tenant_objects.for_request(request).order_by(
        "-is_active", "name"
    )
    return render(
        request,
        "locations/list.html",
        {
            "organization": request.organization,  # type: ignore[attr-defined]
            "locations": locations,
        },
    )


@permission_required(Role.ADMIN)
def create(request: HttpRequest, slug: str) -> HttpResponse:
    organization = request.organization  # type: ignore[attr-defined]
    if request.method == "POST":
        form = LocationForm(request.POST, organization=organization)
        if form.is_valid():
            form.instance.organization = organization
            form.save()
            return redirect("core:settings_locations", slug=slug)
    else:
        form = LocationForm(organization=organization)
    return render(
        request,
        "locations/create.html",
        {"organization": organization, "form": form},
    )


@permission_required(Role.ADMIN)
def edit(request: HttpRequest, slug: str, pk: int) -> HttpResponse:
    organization = request.organization  # type: ignore[attr-defined]
    location = get_object_or_404(
        Location.tenant_objects.for_request(request), pk=pk
    )
    if request.method == "POST":
        form = LocationForm(
            request.POST,
            instance=location,
            organization=organization,
            editing=True,
        )
        if form.is_valid():
            form.save()
            return redirect("core:settings_locations", slug=slug)
    else:
        form = LocationForm(
            instance=location, organization=organization, editing=True
        )
    return render(
        request,
        "locations/edit.html",
        {
            "organization": organization,
            "form": form,
            "location": location,
        },
    )


@require_POST
@permission_required(Role.ADMIN)
def deactivate(request: HttpRequest, slug: str, pk: int) -> HttpResponse:
    location = get_object_or_404(
        Location.tenant_objects.for_request(request), pk=pk
    )
    location_service.deactivate_location(location)
    if request.htmx:  # type: ignore[attr-defined]
        return _row(request, location)
    return redirect("core:settings_locations", slug=slug)


@require_POST
@permission_required(Role.ADMIN)
def reactivate(request: HttpRequest, slug: str, pk: int) -> HttpResponse:
    location = get_object_or_404(
        Location.tenant_objects.for_request(request), pk=pk
    )
    location_service.reactivate_location(location)
    if request.htmx:  # type: ignore[attr-defined]
        return _row(request, location)
    return redirect("core:settings_locations", slug=slug)


def _operator_chip(
    request: HttpRequest,
    location: Location,
    user: User,
    *,
    is_active: bool,
) -> HttpResponse:
    return render(
        request,
        "locations/_operator_chip.html",
        {
            "organization": request.organization,  # type: ignore[attr-defined]
            "location": location,
            "operator": user,
            "is_active": is_active,
        },
    )


@permission_required(Role.ADMIN)
def detail(request: HttpRequest, slug: str, pk: int) -> HttpResponse:  # noqa: ARG001
    organization = request.organization  # type: ignore[attr-defined]
    location = get_object_or_404(
        Location.tenant_objects.for_request(request), pk=pk
    )
    operator_memberships = (
        OrganizationMembership.tenant_objects.for_request(request)
        .filter(role=Role.OPERATOR, is_active=True)
        .select_related("user")
        .order_by("user__email")
    )
    active_user_ids = set(
        LocationMembership.tenant_objects.for_request(request)
        .filter(location=location, is_active=True)
        .values_list("user_id", flat=True)
    )
    return render(
        request,
        "locations/detail.html",
        {
            "organization": organization,
            "location": location,
            "operator_memberships": operator_memberships,
            "active_user_ids": active_user_ids,
        },
    )


@require_POST
@permission_required(Role.ADMIN)
def toggle_operator(
    request: HttpRequest,
    slug: str,  # noqa: ARG001
    pk: int,
    upk: int,
) -> HttpResponse:
    location = get_object_or_404(
        Location.tenant_objects.for_request(request),
        pk=pk,
        is_active=True,
    )
    operator_membership = get_object_or_404(
        OrganizationMembership.tenant_objects.for_request(
            request
        ).select_related("user"),
        user_id=upk,
        role=Role.OPERATOR,
        is_active=True,
    )
    _, is_active = membership_service.toggle_location_membership(
        user=operator_membership.user,
        location=location,
        by=request.user,  # type: ignore[arg-type]
    )
    return _operator_chip(
        request, location, operator_membership.user, is_active=is_active
    )
