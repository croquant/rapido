from django import template
from django.contrib.auth.models import AbstractBaseUser, AnonymousUser

from core.models import OrganizationMembership

register = template.Library()


@register.simple_tag
def get_org_switcher_memberships(
    user: AbstractBaseUser | AnonymousUser | None,
) -> list[OrganizationMembership] | None:
    if user is None or not user.is_authenticated:
        return None
    cached = getattr(user, "_org_switcher_memberships", None)
    if cached is not None:
        return cached or None
    # Cross-tenant by design: the switcher needs every active membership
    # the user has, before any tenant context exists.
    memberships = list(
        OrganizationMembership.objects.filter(
            user=user, is_active=True, organization__is_active=True
        )
        .select_related("organization")
        .order_by("organization__name")
    )
    result = memberships if len(memberships) > 1 else []
    user._org_switcher_memberships = result  # type: ignore[attr-defined]
    return result or None
