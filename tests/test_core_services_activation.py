from unittest.mock import patch

import pytest
from django.core import signing
from django.db import connection
from django.test.utils import CaptureQueriesContext

from core.models import Role
from core.services.activation import activate_from_token
from core.services.exceptions import (
    AlreadyActiveError,
    NoAdminMembershipError,
)
from core.services.tokens import VERIFY_SALT, make_token
from tests.factories import (
    OrganizationFactory,
    OrganizationMembershipFactory,
    UserFactory,
)


@pytest.mark.django_db
def test_activate_flips_both_flags_and_returns_user() -> None:
    user = UserFactory(is_active=False)
    org = OrganizationFactory(is_active=False)
    OrganizationMembershipFactory(user=user, organization=org, role=Role.ADMIN)
    token = make_token(user, salt=VERIFY_SALT)

    result = activate_from_token(token)

    user.refresh_from_db()
    org.refresh_from_db()
    assert result == user
    assert user.is_active is True
    assert org.is_active is True


@pytest.mark.django_db
def test_already_active_user_raises() -> None:
    user = UserFactory(is_active=False)
    org = OrganizationFactory(is_active=False)
    OrganizationMembershipFactory(user=user, organization=org, role=Role.ADMIN)
    token = make_token(user, salt=VERIFY_SALT)

    activate_from_token(token)
    with pytest.raises(AlreadyActiveError):
        activate_from_token(token)


@pytest.mark.django_db
def test_bad_signature_propagates() -> None:
    with pytest.raises(signing.BadSignature):
        activate_from_token("not-a-real-token")


@pytest.mark.django_db
def test_signature_expired_propagates() -> None:
    user = UserFactory(is_active=False)
    org = OrganizationFactory(is_active=False)
    OrganizationMembershipFactory(user=user, organization=org, role=Role.ADMIN)
    token = make_token(user, salt=VERIFY_SALT)
    with (
        patch(
            "core.services.activation.verify_token",
            side_effect=signing.SignatureExpired("expired"),
        ),
        pytest.raises(signing.SignatureExpired),
    ):
        activate_from_token(token)


@pytest.mark.django_db
def test_no_active_admin_membership_raises() -> None:
    user = UserFactory(is_active=False)
    org = OrganizationFactory(is_active=False)
    OrganizationMembershipFactory(
        user=user, organization=org, role=Role.OPERATOR
    )
    token = make_token(user, salt=VERIFY_SALT)
    with pytest.raises(NoAdminMembershipError):
        activate_from_token(token)


@pytest.mark.django_db(transaction=True)
def test_activation_uses_select_for_update() -> None:
    if connection.vendor == "sqlite":
        pytest.skip("SQLite ignores SELECT ... FOR UPDATE")
    user = UserFactory(is_active=False)
    org = OrganizationFactory(is_active=False)
    OrganizationMembershipFactory(user=user, organization=org, role=Role.ADMIN)
    token = make_token(user, salt=VERIFY_SALT)

    with CaptureQueriesContext(connection) as ctx:
        activate_from_token(token)

    sqls = [q["sql"].upper() for q in ctx.captured_queries]
    locked = [s for s in sqls if "FOR UPDATE" in s]
    assert len(locked) >= 2
