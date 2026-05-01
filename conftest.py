import pytest

from core.models import Role, User
from tests.factories import (
    LocationFactory,
    LocationMembershipFactory,
    OrganizationMembershipFactory,
    UserFactory,
)

USER_PASSWORD = "password"


@pytest.fixture
def platform_staff_user(db: None) -> User:  # noqa: ARG001
    return UserFactory(superuser=True)


@pytest.fixture
def org_admin_user(db: None) -> User:  # noqa: ARG001
    user = UserFactory()
    OrganizationMembershipFactory(user=user, role=Role.ADMIN)
    return user


@pytest.fixture
def operator_with_locations(db: None) -> User:  # noqa: ARG001
    user = UserFactory()
    org_membership = OrganizationMembershipFactory(
        user=user, role=Role.OPERATOR
    )
    org = org_membership.organization
    LocationMembershipFactory(
        user=user, location=LocationFactory(organization=org)
    )
    LocationMembershipFactory(
        user=user, location=LocationFactory(organization=org)
    )
    return user


@pytest.fixture
def operator_without_locations(db: None) -> User:  # noqa: ARG001
    user = UserFactory()
    OrganizationMembershipFactory(user=user, role=Role.OPERATOR)
    return user
