from django.db import transaction

from core.models import Organization, OrganizationMembership, Role, User
from core.services.exceptions import LastActiveAdminError


def _other_qualifying_admin_exists(
    organization: Organization,
    *,
    exclude_membership: OrganizationMembership | None = None,
    exclude_user: User | None = None,
) -> bool:
    qs = OrganizationMembership.objects.filter(
        organization=organization,
        role=Role.ADMIN,
        is_active=True,
        user__is_active=True,
    )
    if exclude_membership is not None:
        qs = qs.exclude(pk=exclude_membership.pk)
    if exclude_user is not None:
        qs = qs.exclude(user=exclude_user)
    return qs.exists()


def deactivate_membership(membership: OrganizationMembership) -> None:
    if not membership.is_active:
        return
    with transaction.atomic():
        # Lock the org row first so concurrent admin-changing writes on
        # this org serialize on it (prevents the AB-BA race where two
        # co-admins demote each other and both pass the invariant check).
        Organization.objects.select_for_update().get(
            pk=membership.organization.pk
        )
        locked = (
            OrganizationMembership.objects.select_for_update()
            .select_related("organization")
            .get(pk=membership.pk)
        )
        if not locked.is_active:
            return
        is_qualifying = locked.role == Role.ADMIN and locked.user.is_active
        if is_qualifying and not _other_qualifying_admin_exists(
            locked.organization, exclude_membership=locked
        ):
            raise LastActiveAdminError([locked.organization])
        locked.is_active = False
        locked.save(update_fields=["is_active", "updated_at"])
        membership.is_active = False
        membership.updated_at = locked.updated_at


def change_role(
    membership: OrganizationMembership, new_role: Role | str
) -> None:
    if new_role not in Role.values:
        raise ValueError(f"Unknown role: {new_role!r}")
    if membership.role == new_role:
        return
    with transaction.atomic():
        Organization.objects.select_for_update().get(
            pk=membership.organization.pk
        )
        locked = (
            OrganizationMembership.objects.select_for_update()
            .select_related("organization")
            .get(pk=membership.pk)
        )
        if locked.role == new_role:
            return
        demoting_qualifier = (
            locked.role == Role.ADMIN
            and new_role != Role.ADMIN
            and locked.is_active
            and locked.user.is_active
        )
        if demoting_qualifier and not _other_qualifying_admin_exists(
            locked.organization, exclude_membership=locked
        ):
            raise LastActiveAdminError([locked.organization])
        locked.role = new_role
        locked.save(update_fields=["role", "updated_at"])
        membership.role = new_role
        membership.updated_at = locked.updated_at


def deactivate_user(user: User) -> None:
    if not user.is_active:
        return
    with transaction.atomic():
        locked_user = User.objects.select_for_update().get(pk=user.pk)
        if not locked_user.is_active:
            return
        admin_memberships = list(
            OrganizationMembership.objects.select_related("organization")
            .filter(user=locked_user, role=Role.ADMIN, is_active=True)
            .order_by("organization_id")
        )
        if admin_memberships:
            org_ids = [m.organization.pk for m in admin_memberships]
            # Lock all involved org rows in pk order to avoid deadlocks
            # against concurrent invariant-affecting writes on those orgs.
            list(
                Organization.objects.select_for_update()
                .filter(pk__in=org_ids)
                .order_by("pk")
            )
            offending = sorted(
                (
                    m.organization
                    for m in admin_memberships
                    if not _other_qualifying_admin_exists(
                        m.organization, exclude_user=locked_user
                    )
                ),
                key=lambda o: o.slug,
            )
            if offending:
                raise LastActiveAdminError(offending)
        locked_user.is_active = False
        locked_user.save(update_fields=["is_active", "updated_at"])
        user.is_active = False
        user.updated_at = locked_user.updated_at
