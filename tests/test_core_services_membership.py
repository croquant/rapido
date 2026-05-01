import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext

from core.models import OrganizationMembership, Role
from core.services.exceptions import LastActiveAdminError
from core.services.membership import (
    change_role,
    deactivate_membership,
    deactivate_user,
)
from tests.factories import (
    OrganizationFactory,
    OrganizationMembershipFactory,
    UserFactory,
)

# ---- deactivate_membership -------------------------------------------------


@pytest.mark.django_db
def test_deactivate_membership_succeeds_for_operator() -> None:
    m = OrganizationMembershipFactory(role=Role.OPERATOR)
    deactivate_membership(m)
    m.refresh_from_db()
    assert m.is_active is False


@pytest.mark.django_db
def test_deactivate_membership_succeeds_for_non_last_admin() -> None:
    org = OrganizationFactory()
    m1 = OrganizationMembershipFactory(organization=org, role=Role.ADMIN)
    OrganizationMembershipFactory(organization=org, role=Role.ADMIN)
    deactivate_membership(m1)
    m1.refresh_from_db()
    assert m1.is_active is False


@pytest.mark.django_db
def test_deactivate_membership_raises_for_last_admin() -> None:
    org = OrganizationFactory()
    m = OrganizationMembershipFactory(organization=org, role=Role.ADMIN)
    with pytest.raises(LastActiveAdminError) as exc:
        deactivate_membership(m)
    assert exc.value.organizations == [org]
    m.refresh_from_db()
    assert m.is_active is True


@pytest.mark.django_db
def test_deactivate_membership_idempotent_on_already_inactive() -> None:
    m = OrganizationMembershipFactory(role=Role.OPERATOR, is_active=False)
    before = m.updated_at
    deactivate_membership(m)
    m.refresh_from_db()
    assert m.is_active is False
    assert m.updated_at == before


@pytest.mark.django_db
def test_deactivate_membership_inactive_user_admin_does_not_count() -> None:
    org = OrganizationFactory()
    inactive = UserFactory(is_active=False)
    OrganizationMembershipFactory(
        user=inactive, organization=org, role=Role.ADMIN
    )
    sole_qualifying = OrganizationMembershipFactory(
        organization=org, role=Role.ADMIN
    )
    with pytest.raises(LastActiveAdminError):
        deactivate_membership(sole_qualifying)


@pytest.mark.django_db
def test_deactivate_membership_when_self_user_inactive_succeeds() -> None:
    org = OrganizationFactory()
    inactive = UserFactory(is_active=False)
    m = OrganizationMembershipFactory(
        user=inactive, organization=org, role=Role.ADMIN
    )
    deactivate_membership(m)
    m.refresh_from_db()
    assert m.is_active is False


@pytest.mark.django_db
def test_deactivate_membership_does_not_affect_other_orgs() -> None:
    user = UserFactory()
    org_a = OrganizationFactory()
    org_b = OrganizationFactory()
    OrganizationMembershipFactory(organization=org_a, role=Role.ADMIN)
    OrganizationMembershipFactory(organization=org_b, role=Role.ADMIN)
    m_a = OrganizationMembershipFactory(
        user=user, organization=org_a, role=Role.ADMIN
    )
    m_b = OrganizationMembershipFactory(
        user=user, organization=org_b, role=Role.ADMIN
    )
    deactivate_membership(m_a)
    m_a.refresh_from_db()
    m_b.refresh_from_db()
    assert m_a.is_active is False
    assert m_b.is_active is True


# ---- change_role -----------------------------------------------------------


@pytest.mark.django_db
def test_change_role_promotes_operator_to_admin() -> None:
    m = OrganizationMembershipFactory(role=Role.OPERATOR)
    change_role(m, Role.ADMIN)
    m.refresh_from_db()
    assert m.role == Role.ADMIN


@pytest.mark.django_db
def test_change_role_demotes_non_last_admin() -> None:
    org = OrganizationFactory()
    m = OrganizationMembershipFactory(organization=org, role=Role.ADMIN)
    OrganizationMembershipFactory(organization=org, role=Role.ADMIN)
    change_role(m, Role.OPERATOR)
    m.refresh_from_db()
    assert m.role == Role.OPERATOR


@pytest.mark.django_db
def test_change_role_demoting_last_admin_raises() -> None:
    org = OrganizationFactory()
    m = OrganizationMembershipFactory(organization=org, role=Role.ADMIN)
    with pytest.raises(LastActiveAdminError) as exc:
        change_role(m, Role.OPERATOR)
    assert exc.value.organizations == [org]
    m.refresh_from_db()
    assert m.role == Role.ADMIN


@pytest.mark.django_db
def test_change_role_same_role_is_noop() -> None:
    m = OrganizationMembershipFactory(role=Role.ADMIN)
    before = m.updated_at
    with CaptureQueriesContext(connection) as ctx:
        change_role(m, Role.ADMIN)
    assert len(ctx.captured_queries) == 0
    m.refresh_from_db()
    assert m.updated_at == before


@pytest.mark.django_db
def test_change_role_unknown_role_raises_value_error() -> None:
    m = OrganizationMembershipFactory(role=Role.ADMIN)
    with pytest.raises(ValueError, match="Unknown role"):
        change_role(m, "WIZARD")
    m.refresh_from_db()
    assert m.role == Role.ADMIN


@pytest.mark.django_db
def test_change_role_demoting_inactive_admin_succeeds() -> None:
    org = OrganizationFactory()
    m = OrganizationMembershipFactory(
        organization=org, role=Role.ADMIN, is_active=False
    )
    change_role(m, Role.OPERATOR)
    m.refresh_from_db()
    assert m.role == Role.OPERATOR


@pytest.mark.django_db
def test_change_role_demoting_admin_with_inactive_user_succeeds() -> None:
    org = OrganizationFactory()
    inactive = UserFactory(is_active=False)
    m = OrganizationMembershipFactory(
        user=inactive, organization=org, role=Role.ADMIN
    )
    change_role(m, Role.OPERATOR)
    m.refresh_from_db()
    assert m.role == Role.OPERATOR


# ---- deactivate_user -------------------------------------------------------


@pytest.mark.django_db
def test_deactivate_user_idempotent_on_already_inactive() -> None:
    user = UserFactory(is_active=False)
    before = user.updated_at
    deactivate_user(user)
    user.refresh_from_db()
    assert user.is_active is False
    assert user.updated_at == before


@pytest.mark.django_db
def test_deactivate_user_with_no_memberships_succeeds() -> None:
    user = UserFactory()
    deactivate_user(user)
    user.refresh_from_db()
    assert user.is_active is False


@pytest.mark.django_db
def test_deactivate_user_with_only_operator_memberships_succeeds() -> None:
    user = UserFactory()
    OrganizationMembershipFactory(user=user, role=Role.OPERATOR)
    OrganizationMembershipFactory(user=user, role=Role.OPERATOR)
    deactivate_user(user)
    user.refresh_from_db()
    assert user.is_active is False


@pytest.mark.django_db
def test_deactivate_user_as_co_admin_succeeds() -> None:
    org = OrganizationFactory()
    user = UserFactory()
    OrganizationMembershipFactory(user=user, organization=org, role=Role.ADMIN)
    OrganizationMembershipFactory(organization=org, role=Role.ADMIN)
    deactivate_user(user)
    user.refresh_from_db()
    assert user.is_active is False


@pytest.mark.django_db
def test_deactivate_user_as_sole_admin_raises() -> None:
    org = OrganizationFactory()
    user = UserFactory()
    OrganizationMembershipFactory(user=user, organization=org, role=Role.ADMIN)
    with pytest.raises(LastActiveAdminError) as exc:
        deactivate_user(user)
    assert exc.value.organizations == [org]
    user.refresh_from_db()
    assert user.is_active is True


@pytest.mark.django_db
def test_deactivate_user_aggregates_multiple_offending_orgs() -> None:
    user = UserFactory()
    org_a = OrganizationFactory(slug="aaa")
    org_b = OrganizationFactory(slug="bbb")
    OrganizationMembershipFactory(
        user=user, organization=org_a, role=Role.ADMIN
    )
    OrganizationMembershipFactory(
        user=user, organization=org_b, role=Role.ADMIN
    )
    with pytest.raises(LastActiveAdminError) as exc:
        deactivate_user(user)
    assert [o.slug for o in exc.value.organizations] == ["aaa", "bbb"]
    user.refresh_from_db()
    assert user.is_active is True


@pytest.mark.django_db
def test_deactivate_user_inactive_admin_membership_excluded() -> None:
    user = UserFactory()
    org = OrganizationFactory()
    OrganizationMembershipFactory(organization=org, role=Role.ADMIN)
    OrganizationMembershipFactory(
        user=user, organization=org, role=Role.ADMIN, is_active=False
    )
    deactivate_user(user)
    user.refresh_from_db()
    assert user.is_active is False


@pytest.mark.django_db
def test_deactivate_user_does_not_modify_memberships() -> None:
    user = UserFactory()
    org = OrganizationFactory()
    OrganizationMembershipFactory(organization=org, role=Role.ADMIN)
    m_admin = OrganizationMembershipFactory(
        user=user, organization=org, role=Role.ADMIN
    )
    m_op = OrganizationMembershipFactory(user=user, role=Role.OPERATOR)
    deactivate_user(user)
    m_admin.refresh_from_db()
    m_op.refresh_from_db()
    assert m_admin.is_active is True
    assert m_op.is_active is True
    assert OrganizationMembership.objects.filter(user=user).count() == 2
