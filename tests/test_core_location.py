import uuid

import pytest
from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.db.models import ProtectedError

from core.models import Location
from tests.factories import LocationFactory, OrganizationFactory


@pytest.mark.django_db
def test_location_defaults() -> None:
    org = OrganizationFactory()
    loc = Location.objects.create(
        organization=org,
        name="Frituur Centrum",
        slug="centrum",
        street="Grote Markt 1",
        postal_code="1000",
        city="Brussels",
    )
    assert loc.is_active is True
    assert loc.phone == ""
    assert isinstance(loc.public_id, uuid.UUID)
    assert loc.created_at is not None
    assert loc.updated_at is not None


@pytest.mark.django_db
def test_public_id_is_uuid7() -> None:
    loc = LocationFactory()
    assert loc.public_id.version == 7


@pytest.mark.django_db
def test_str_returns_name() -> None:
    loc = LocationFactory(name="Frituur Janssens")
    assert str(loc) == "Frituur Janssens"


@pytest.mark.django_db
def test_slug_unique_within_org() -> None:
    org = OrganizationFactory()
    LocationFactory(organization=org, slug="centrum")
    with pytest.raises(IntegrityError):
        LocationFactory(organization=org, slug="centrum")


@pytest.mark.django_db
def test_slug_not_unique_across_orgs() -> None:
    org_a = OrganizationFactory()
    org_b = OrganizationFactory()
    LocationFactory(organization=org_a, slug="centrum")
    LocationFactory(organization=org_b, slug="centrum")
    assert Location.objects.filter(slug="centrum").count() == 2


@pytest.mark.django_db
def test_protect_on_org_delete() -> None:
    loc = LocationFactory()
    with pytest.raises(ProtectedError):
        loc.organization.delete()


@pytest.mark.django_db
def test_org_delete_succeeds_after_locations_removed() -> None:
    loc = LocationFactory()
    org = loc.organization
    loc.delete()
    org.delete()
    assert not Location.objects.filter(organization_id=org.pk).exists()


@pytest.mark.django_db
def test_slug_validator_rejects_uppercase() -> None:
    org = OrganizationFactory()
    loc = Location(
        organization=org,
        name="A",
        slug="Foo",
        street="x",
        postal_code="1000",
        city="Brussels",
    )
    with pytest.raises(ValidationError):
        loc.full_clean()


@pytest.mark.django_db
def test_slug_validator_rejects_spaces() -> None:
    org = OrganizationFactory()
    loc = Location(
        organization=org,
        name="A",
        slug="foo bar",
        street="x",
        postal_code="1000",
        city="Brussels",
    )
    with pytest.raises(ValidationError):
        loc.full_clean()


@pytest.mark.django_db
def test_required_address_fields_blank_rejected() -> None:
    org = OrganizationFactory()
    loc = Location(
        organization=org,
        name="A",
        slug="a",
        street="",
        postal_code="",
        city="",
    )
    with pytest.raises(ValidationError) as exc:
        loc.full_clean()
    errors = exc.value.message_dict
    assert "street" in errors
    assert "postal_code" in errors
    assert "city" in errors


@pytest.mark.django_db
def test_phone_blank_allowed() -> None:
    org = OrganizationFactory()
    loc = Location(
        organization=org,
        name="A",
        slug="a",
        street="x",
        postal_code="1000",
        city="Brussels",
        phone="",
    )
    loc.full_clean()
