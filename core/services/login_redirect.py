from core.models import OrganizationMembership, User


def login_redirect_for(user: User) -> str:
    # Whitepaper epic 2b §4 redirect rule. OPERATOR with single
    # LocationMembership -> /o/<slug>/l/<lslug>/pos/ refinement is deferred
    # to issue #56 once the picker and POS routes exist.
    memberships = list(
        OrganizationMembership.objects.filter(user=user, is_active=True)
        .select_related("organization")
        .order_by("created_at")
    )
    if len(memberships) == 1:
        return f"/o/{memberships[0].organization.slug}/"
    return "/orgs/"
