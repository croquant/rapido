from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect, render

from core.decorators import permission_required
from core.models import LocationMembership, OrganizationMembership, Role


@permission_required()
def dashboard(request: HttpRequest, slug: str) -> HttpResponse:  # noqa: ARG001
    org = request.organization  # type: ignore[attr-defined]
    user = request.user

    if user.is_superuser:
        role = Role.ADMIN
    else:
        membership = OrganizationMembership.objects.get(
            user=user, organization=org, is_active=True
        )
        role = membership.role

    if role == Role.OPERATOR:
        loc_slugs = list(
            LocationMembership.objects.filter(
                user=user,
                is_active=True,
                location__organization=org,
                location__is_active=True,
            ).values_list("location__slug", flat=True)[:2]
        )
        if len(loc_slugs) == 1:
            return redirect(f"/o/{org.slug}/l/{loc_slugs[0]}/pos/")
        return redirect(f"/o/{org.slug}/pos/")

    return render(
        request,
        "dashboard/index.html",
        {"organization": org},
    )
