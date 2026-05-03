from django.http import HttpRequest, HttpResponse

from core.decorators import permission_required
from core.models import Role


@permission_required(Role.ADMIN)
def settings_members(request: HttpRequest, slug: str) -> HttpResponse:  # noqa: ARG001
    return HttpResponse("TODO: members settings")


@permission_required(Role.ADMIN)
def settings_invitations(request: HttpRequest, slug: str) -> HttpResponse:  # noqa: ARG001
    return HttpResponse("TODO: invitations settings")


@permission_required(Role.ADMIN)
def settings_organization(request: HttpRequest, slug: str) -> HttpResponse:  # noqa: ARG001
    return HttpResponse("TODO: organization settings")
