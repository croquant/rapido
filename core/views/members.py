from django.db.models import Q
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from core.decorators import permission_required
from core.forms.invitation import InvitationForm
from core.forms.member import RoleChangeForm
from core.models import (
    Invitation,
    Location,
    LocationMembership,
    OrganizationMembership,
    Role,
)
from core.services import membership as membership_service
from core.services.exceptions import LastActiveAdminError


def _row(
    request: HttpRequest, membership: OrganizationMembership
) -> HttpResponse:
    return render(
        request,
        "members/_row.html",
        {
            "organization": request.organization,  # type: ignore[attr-defined]
            "membership": membership,
        },
    )


def _location_chip(
    request: HttpRequest,
    membership: OrganizationMembership,
    location: Location,
    *,
    is_active: bool,
) -> HttpResponse:
    return render(
        request,
        "members/_location_chip.html",
        {
            "organization": request.organization,  # type: ignore[attr-defined]
            "membership": membership,
            "location": location,
            "is_active": is_active,
        },
    )


@permission_required(Role.ADMIN)
def list_view(request: HttpRequest, slug: str) -> HttpResponse:  # noqa: ARG001
    organization = request.organization  # type: ignore[attr-defined]
    memberships = (
        OrganizationMembership.tenant_objects.for_request(request)
        .select_related("user")
        .order_by("-is_active", "user__email")
    )
    now = timezone.now()
    invitations = Invitation.tenant_objects.for_request(request).filter(
        accepted_at__isnull=True
    )
    pending = invitations.filter(
        revoked_at__isnull=True, expires_at__gt=now
    ).order_by("-created_at")
    archive = invitations.filter(
        Q(revoked_at__isnull=False) | Q(expires_at__lte=now)
    ).order_by("-created_at")
    return render(
        request,
        "members/list.html",
        {
            "organization": organization,
            "memberships": memberships,
            "pending_invitations": pending,
            "archived_invitations": archive,
            "invite_form": InvitationForm(organization=organization),
        },
    )


@permission_required(Role.ADMIN)
def detail(request: HttpRequest, slug: str, pk: int) -> HttpResponse:  # noqa: ARG001
    organization = request.organization  # type: ignore[attr-defined]
    membership = get_object_or_404(
        OrganizationMembership.tenant_objects.for_request(
            request
        ).select_related("user"),
        pk=pk,
    )
    locations = (
        Location.tenant_objects.for_organization(organization)
        .filter(is_active=True)
        .order_by("name")
    )
    active_loc_ids = set(
        LocationMembership.tenant_objects.for_request(request)
        .filter(
            user=membership.user,
            location__in=locations,
            is_active=True,
        )
        .values_list("location_id", flat=True)
    )
    return render(
        request,
        "members/detail.html",
        {
            "organization": organization,
            "membership": membership,
            "locations": locations,
            "active_location_ids": active_loc_ids,
        },
    )


@require_POST
@permission_required(Role.ADMIN)
def change_role(
    request: HttpRequest,
    slug: str,  # noqa: ARG001
    pk: int,
) -> HttpResponse:
    organization = request.organization  # type: ignore[attr-defined]
    membership = get_object_or_404(
        OrganizationMembership.tenant_objects.for_request(
            request
        ).select_related("user"),
        pk=pk,
    )
    form = RoleChangeForm(request.POST)
    if not form.is_valid():
        response = _row(request, membership)
        response.status_code = 422
        return response
    try:
        membership_service.change_role(membership, form.cleaned_data["role"])
    except LastActiveAdminError:
        membership.refresh_from_db()
        response = _row(request, membership)
        response.status_code = 422
        response["HX-Trigger"] = "members:role_change_failed"
        return response
    if request.htmx:  # type: ignore[attr-defined]
        return _row(request, membership)
    return redirect("core:settings_members", slug=organization.slug)


@require_POST
@permission_required(Role.ADMIN)
def deactivate(
    request: HttpRequest,
    slug: str,  # noqa: ARG001
    pk: int,
) -> HttpResponse:
    organization = request.organization  # type: ignore[attr-defined]
    membership = get_object_or_404(
        OrganizationMembership.tenant_objects.for_request(
            request
        ).select_related("user"),
        pk=pk,
    )
    try:
        membership_service.deactivate_membership(membership)
    except LastActiveAdminError:
        membership.refresh_from_db()
        response = _row(request, membership)
        response.status_code = 422
        response["HX-Trigger"] = "members:deactivate_failed"
        return response
    if request.htmx:  # type: ignore[attr-defined]
        return _row(request, membership)
    return redirect("core:settings_members", slug=organization.slug)


@require_POST
@permission_required(Role.ADMIN)
def reactivate(
    request: HttpRequest,
    slug: str,  # noqa: ARG001
    pk: int,
) -> HttpResponse:
    organization = request.organization  # type: ignore[attr-defined]
    membership = get_object_or_404(
        OrganizationMembership.tenant_objects.for_request(
            request
        ).select_related("user"),
        pk=pk,
    )
    membership_service.reactivate_membership(membership)
    if request.htmx:  # type: ignore[attr-defined]
        return _row(request, membership)
    return redirect("core:settings_members", slug=organization.slug)


@require_POST
@permission_required(Role.ADMIN)
def toggle_location(
    request: HttpRequest,
    slug: str,  # noqa: ARG001
    pk: int,
    lpk: int,
) -> HttpResponse:
    membership = get_object_or_404(
        OrganizationMembership.tenant_objects.for_request(
            request
        ).select_related("user"),
        pk=pk,
    )
    location = get_object_or_404(
        Location.tenant_objects.for_request(request),
        pk=lpk,
        is_active=True,
    )
    _, is_active = membership_service.toggle_location_membership(
        user=membership.user,
        location=location,
        by=request.user,  # type: ignore[arg-type]
    )
    return _location_chip(request, membership, location, is_active=is_active)
