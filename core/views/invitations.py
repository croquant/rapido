from django.contrib.auth import login as auth_login
from django.contrib.auth import logout as auth_logout
from django.core import signing
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from django.views.decorators.http import require_POST

from core.decorators import permission_required
from core.forms.invitation import InvitationForm, InviteAcceptForm
from core.models import Invitation, OrganizationMembership, Role, User
from core.services import invitation as invitation_service
from core.services.exceptions import (
    AlreadyMemberError,
    BadStateError,
    OperatorRequiresLocationsError,
    WeakPasswordError,
)
from core.services.login_redirect import login_redirect_for
from core.services.tokens import verify_invite_token


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


def _accept_error(
    request: HttpRequest,
    *,
    reason: str,
    organization: object | None = None,
    invitation: Invitation | None = None,
    stale_locations: list[object] | None = None,
) -> HttpResponse:
    return render(
        request,
        "invitations/accept_error.html",
        {
            "reason": reason,
            "organization": organization,
            "invitation": invitation,
            "stale_locations": stale_locations or [],
        },
    )


def accept(request: HttpRequest, token: str) -> HttpResponse:
    try:
        payload = verify_invite_token(token)
    except signing.BadSignature:
        return _accept_error(request, reason="invalid_token")

    invitation_id = payload.get("invitation_id")
    if not invitation_id:
        return _accept_error(request, reason="invalid_token")

    invitation = (
        Invitation.objects.select_related("organization")  # noqa: tenant-lint
        .prefetch_related("locations")
        .filter(pk=invitation_id)
        .first()
    )
    if invitation is None:
        return _accept_error(request, reason="invalid_token")

    organization = invitation.organization

    if invitation.accepted_at is not None:
        return _accept_error(
            request,
            reason="already_accepted",
            organization=organization,
            invitation=invitation,
        )
    if invitation.revoked_at is not None:
        return _accept_error(
            request,
            reason="already_revoked",
            organization=organization,
            invitation=invitation,
        )
    if invitation.expires_at < timezone.now():
        return _accept_error(
            request,
            reason="expired",
            organization=organization,
            invitation=invitation,
        )

    invite_locations = list(invitation.locations.all())
    stale = [loc for loc in invite_locations if not loc.is_active]
    if stale:
        return _accept_error(
            request,
            reason="stale_locations",
            organization=organization,
            invitation=invitation,
            stale_locations=stale,
        )

    existing_user = User.objects.filter(  # noqa: tenant-lint
        email__iexact=invitation.email
    ).first()
    if existing_user is not None:
        active_membership = OrganizationMembership.objects.filter(  # noqa: tenant-lint
            user=existing_user,
            organization=organization,
            is_active=True,
        ).exists()
        if active_membership:
            return _accept_error(
                request,
                reason="already_member",
                organization=organization,
                invitation=invitation,
            )

    if request.method == "POST":
        # Mismatched authenticated user: clear the wrong session before
        # processing the accept (no-op on GET to keep it side-effect-free,
        # since /invite/<token>/ is publicly reachable and a GET-side
        # logout would be a CSRF-style logout vector).
        if (
            request.user.is_authenticated
            and (request.user.email or "").lower() != invitation.email  # type: ignore[union-attr]
        ):
            auth_logout(request)
        if existing_user is None:
            form = InviteAcceptForm(request.POST)
            if not form.is_valid():
                response = render(
                    request,
                    "invitations/accept_set_password.html",
                    {
                        "organization": organization,
                        "invitation": invitation,
                        "invite_locations": invite_locations,
                        "form": form,
                    },
                )
                response.status_code = 422
                return response
            try:
                user = invitation_service.accept_invitation(
                    token, password=form.cleaned_data["new_password"]
                )
            except WeakPasswordError as exc:
                for message in exc.messages:
                    form.add_error("new_password", message)
                response = render(
                    request,
                    "invitations/accept_set_password.html",
                    {
                        "organization": organization,
                        "invitation": invitation,
                        "invite_locations": invite_locations,
                        "form": form,
                    },
                )
                response.status_code = 422
                return response
            except BadStateError as exc:
                return _accept_error(
                    request,
                    reason=exc.reason,
                    organization=organization,
                    invitation=invitation,
                )
        else:
            try:
                user = invitation_service.accept_invitation(token)
            except BadStateError as exc:
                return _accept_error(
                    request,
                    reason=exc.reason,
                    organization=organization,
                    invitation=invitation,
                )

        auth_login(request, user)
        return redirect(login_redirect_for(user))

    if existing_user is not None:
        return render(
            request,
            "invitations/accept_existing.html",
            {
                "organization": organization,
                "invitation": invitation,
                "invite_locations": invite_locations,
            },
        )
    return render(
        request,
        "invitations/accept_set_password.html",
        {
            "organization": organization,
            "invitation": invitation,
            "invite_locations": invite_locations,
            "form": InviteAcceptForm(),
        },
    )
