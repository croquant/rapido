from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect, render

from core.decorators import permission_required
from core.forms.organization import OrganizationSettingsForm
from core.models import Role


@permission_required(Role.ADMIN)
def settings_view(request: HttpRequest, slug: str) -> HttpResponse:
    organization = request.organization  # type: ignore[attr-defined]
    if request.method == "POST":
        form = OrganizationSettingsForm(request.POST, instance=organization)
        if form.is_valid():
            form.save()
            return redirect("core:settings_organization", slug=slug)
    else:
        form = OrganizationSettingsForm(instance=organization)
    return render(
        request,
        "organization/settings.html",
        {"organization": organization, "form": form},
    )
