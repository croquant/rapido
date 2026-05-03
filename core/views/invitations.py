from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.translation import gettext_lazy as _
from django.views.decorators.http import require_POST

from core.decorators import permission_required
from core.forms.invitation import InvitationForm
from core.models import Invitation, Role
from core.services import invitation as invitation_service
from core.services.exceptions import (
    AlreadyMemberError,
    BadStateError,
    OperatorRequiresLocationsError,
)


def _invitation_row(
    request: HttpRequest, invitation: Invitation, *, variant: str
) -> HttpResponse:
    return render(
        request,
        "members/_invitation_row.html",
        {
            "organization": request.organization,  # type: ignore[attr-defined]
            "invitation": invitation,
            "variant": variant,
        },
    )


def _invite_modal(
    request: HttpRequest, form: InvitationForm, *, status: int = 200
) -> HttpResponse:
    response = render(
        request,
        "members/_invite_modal.html",
        {
            "organization": request.organization,  # type: ignore[attr-defined]
            "form": form,
        },
    )
    response.status_code = status
    return response


@require_POST
@permission_required(Role.ADMIN)
def create(request: HttpRequest, slug: str) -> HttpResponse:  # noqa: ARG001
    organization = request.organization  # type: ignore[attr-defined]
    form = InvitationForm(request.POST, organization=organization)
    if not form.is_valid():
        return _invite_modal(request, form, status=422)
    try:
        invitation_service.create_invitation(
            organization=organization,
            email=form.cleaned_data["email"],
            role=form.cleaned_data["role"],
            locations=list(form.cleaned_data.get("locations") or []),
            created_by=request.user,  # type: ignore[arg-type]
        )
    except AlreadyMemberError:
        form.add_error(
            "email",
            _("This person is already an active member of this organization."),
        )
        return _invite_modal(request, form, status=422)
    except OperatorRequiresLocationsError:
        form.add_error(
            "locations",
            _("Operators must be assigned at least one location."),
        )
        return _invite_modal(request, form, status=422)
    except BadStateError as exc:
        if exc.reason == "pending_exists":
            form.add_error(
                "email",
                _("A pending invitation already exists for this email."),
            )
            return _invite_modal(request, form, status=422)
        raise

    list_url = reverse(
        "core:settings_members", kwargs={"slug": organization.slug}
    )
    if request.htmx:  # type: ignore[attr-defined]
        response = HttpResponse(status=204)
        response["HX-Redirect"] = list_url
        response["HX-Trigger"] = "invitations:created"
        return response
    return redirect(list_url)


@require_POST
@permission_required(Role.ADMIN)
def resend(
    request: HttpRequest,
    slug: str,  # noqa: ARG001
    pk: int,
) -> HttpResponse:
    invitation = get_object_or_404(
        Invitation.tenant_objects.for_request(request), pk=pk
    )
    try:
        invitation_service.resend_invitation(invitation)
    except BadStateError:
        response = _invitation_row(request, invitation, variant="pending")
        response.status_code = 422
        response["HX-Trigger"] = "invitations:resend_failed"
        return response
    if request.htmx:  # type: ignore[attr-defined]
        return _invitation_row(request, invitation, variant="pending")
    return redirect(
        "core:settings_members",
        slug=request.organization.slug,  # type: ignore[attr-defined]
    )


@require_POST
@permission_required(Role.ADMIN)
def revoke(
    request: HttpRequest,
    slug: str,  # noqa: ARG001
    pk: int,
) -> HttpResponse:
    invitation = get_object_or_404(
        Invitation.tenant_objects.for_request(request), pk=pk
    )
    invitation_service.revoke_invitation(invitation, by=request.user)  # type: ignore[arg-type]
    if request.htmx:  # type: ignore[attr-defined]
        response = HttpResponse(status=204)
        response["HX-Refresh"] = "true"
        return response
    return redirect(
        "core:settings_members",
        slug=request.organization.slug,  # type: ignore[attr-defined]
    )
