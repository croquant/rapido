from core.models import LocationMembership, OrganizationMembership, Role, User


def login_redirect_for(user: User) -> str:
    # Whitepaper epic 2b §4 redirect rule:
    #   single active org membership -> /o/<slug>/
    #   OPERATOR with exactly one active LocationMembership in that org
    #     -> /o/<slug>/l/<lslug>/pos/
    #   anything else (zero or multiple orgs) -> /orgs/
    memberships = list(
        OrganizationMembership.objects.filter(
            user=user, is_active=True, organization__is_active=True
        )
        .select_related("organization")
        .order_by("created_at")
    )
    if len(memberships) != 1:
        return "/orgs/"
    mem = memberships[0]
    org_slug = mem.organization.slug
    if mem.role == Role.OPERATOR:
        loc_memberships = list(
            LocationMembership.objects.filter(
                user=user,
                is_active=True,
                location__organization=mem.organization,
            )
            .select_related("location")
            .order_by("created_at")[:2]
        )
        if len(loc_memberships) == 1:
            return f"/o/{org_slug}/l/{loc_memberships[0].location.slug}/pos/"
    return f"/o/{org_slug}/"
