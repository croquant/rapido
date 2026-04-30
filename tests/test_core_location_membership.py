import pytest
from django.db import IntegrityError
from django.db.models import ProtectedError

from core.models import LocationMembership
from tests.factories import (
    LocationFactory,
    LocationMembershipFactory,
    UserFactory,
)


@pytest.mark.django_db
def test_default_is_active_and_pin() -> None:
    m = LocationMembershipFactory()
    assert m.is_active is True
    assert m.pin == ""


@pytest.mark.django_db
def test_inherits_timestamps() -> None:
    m = LocationMembershipFactory()
    assert m.created_at is not None
    assert m.updated_at is not None


@pytest.mark.django_db
def test_unique_user_location() -> None:
    user = UserFactory()
    loc = LocationFactory()
    LocationMembershipFactory(user=user, location=loc)
    with pytest.raises(IntegrityError):
        LocationMembershipFactory(user=user, location=loc)


@pytest.mark.django_db
def test_same_user_two_locations_allowed() -> None:
    user = UserFactory()
    LocationMembershipFactory(user=user)
    LocationMembershipFactory(user=user)
    assert user.location_memberships.count() == 2


@pytest.mark.django_db
def test_user_delete_cascades() -> None:
    m = LocationMembershipFactory()
    pk = m.pk
    m.user.delete()
    assert not LocationMembership.objects.filter(pk=pk).exists()


@pytest.mark.django_db
def test_location_delete_cascades() -> None:
    m = LocationMembershipFactory()
    pk = m.pk
    m.location.delete()
    assert not LocationMembership.objects.filter(pk=pk).exists()


@pytest.mark.django_db
def test_created_by_protect() -> None:
    creator = UserFactory()
    LocationMembershipFactory(created_by=creator)
    with pytest.raises(ProtectedError):
        creator.delete()


@pytest.mark.django_db
def test_created_by_nullable() -> None:
    m = LocationMembershipFactory(created_by=None)
    assert m.created_by is None


@pytest.mark.django_db
def test_str_format() -> None:
    m = LocationMembershipFactory()
    s = str(m)
    assert m.user.email in s
    assert m.location.name in s


@pytest.mark.django_db
def test_related_names() -> None:
    m = LocationMembershipFactory()
    assert m.user.location_memberships.filter(pk=m.pk).exists()
    assert m.location.location_memberships.filter(pk=m.pk).exists()
