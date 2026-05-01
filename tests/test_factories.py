import pytest

from tests.factories import (
    LocationFactory,
    LocationMembershipFactory,
    OrganizationFactory,
    OrganizationMembershipFactory,
    UserFactory,
)


@pytest.mark.django_db
def test_each_factory_builds_valid_instance() -> None:
    user = UserFactory()
    assert user.pk is not None
    assert user.is_active is True
    assert user.check_password("password") is True

    staff = UserFactory(staff=True)
    assert staff.is_staff is True and staff.is_superuser is False

    su = UserFactory(superuser=True)
    assert su.is_staff is True and su.is_superuser is True

    org = OrganizationFactory()
    assert org.pk is not None

    loc = LocationFactory()
    assert loc.pk is not None and loc.organization_id is not None

    om = OrganizationMembershipFactory()
    assert om.pk is not None and om.user_id and om.organization_id

    lm = LocationMembershipFactory()
    assert lm.pk is not None and lm.user_id and lm.location_id


def test_factories_have_no_collisions_over_100_builds() -> None:
    emails = {UserFactory.build().email for _ in range(100)}
    assert len(emails) == 100

    org_slugs = {OrganizationFactory.build().slug for _ in range(100)}
    assert len(org_slugs) == 100

    billing_emails = {
        OrganizationFactory.build().billing_email for _ in range(100)
    }
    assert len(billing_emails) == 100

    loc_slugs = {LocationFactory.build().slug for _ in range(100)}
    assert len(loc_slugs) == 100
