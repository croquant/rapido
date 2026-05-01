from core.models import Role, User


def test_platform_staff_user_shape(platform_staff_user: User) -> None:
    assert platform_staff_user.is_superuser is True
    assert platform_staff_user.is_staff is True
    assert platform_staff_user.is_active is True
    assert platform_staff_user.organization_memberships.count() == 0
    assert platform_staff_user.location_memberships.count() == 0


def test_org_admin_user_shape(org_admin_user: User) -> None:
    assert org_admin_user.is_superuser is False
    assert org_admin_user.is_staff is False
    memberships = list(org_admin_user.organization_memberships.all())
    assert len(memberships) == 1
    assert memberships[0].role == Role.ADMIN
    assert memberships[0].is_active is True
    assert org_admin_user.location_memberships.count() == 0


def test_operator_with_locations_shape(
    operator_with_locations: User,
) -> None:
    org_memberships = list(
        operator_with_locations.organization_memberships.all()
    )
    assert len(org_memberships) == 1
    assert org_memberships[0].role == Role.OPERATOR
    assert org_memberships[0].is_active is True

    loc_memberships = list(operator_with_locations.location_memberships.all())
    assert len(loc_memberships) == 2
    org_id = org_memberships[0].organization_id
    for lm in loc_memberships:
        assert lm.is_active is True
        assert lm.location.organization_id == org_id


def test_operator_without_locations_shape(
    operator_without_locations: User,
) -> None:
    org_memberships = list(
        operator_without_locations.organization_memberships.all()
    )
    assert len(org_memberships) == 1
    assert org_memberships[0].role == Role.OPERATOR
    assert org_memberships[0].is_active is True
    assert operator_without_locations.location_memberships.count() == 0
