import uuid
import zoneinfo

import pytest
from django.core.exceptions import ValidationError
from django.db import IntegrityError

from core.models import Organization, TimestampedModel


def test_timestamped_model_is_abstract() -> None:
    assert TimestampedModel._meta.abstract is True


def test_timestamped_model_has_auto_timestamp_fields() -> None:
    fields = {f.name: f for f in TimestampedModel._meta.get_fields()}
    assert fields["created_at"].auto_now_add is True  # type: ignore[attr-defined]
    assert fields["updated_at"].auto_now is True  # type: ignore[attr-defined]


@pytest.mark.django_db
def test_organization_defaults() -> None:
    org = Organization.objects.create(
        name="Frituur Max",
        slug="frituur-max",
        billing_email="owner@example.be",
    )
    assert org.country == "BE"
    assert org.default_timezone == zoneinfo.ZoneInfo("Europe/Brussels")
    assert org.default_currency == "EUR"
    assert org.default_language == "en-US"
    assert org.is_active is False
    assert isinstance(org.public_id, uuid.UUID)
    assert org.created_at is not None
    assert org.updated_at is not None


@pytest.mark.django_db
def test_organization_slug_unique() -> None:
    Organization.objects.create(
        name="A", slug="dup", billing_email="a@example.be"
    )
    with pytest.raises(IntegrityError):
        Organization.objects.create(
            name="B", slug="dup", billing_email="b@example.be"
        )


@pytest.mark.django_db
def test_vat_validator_rejects_blank() -> None:
    org = Organization(
        name="A",
        slug="a",
        billing_email="a@example.be",
        vat_number="",
    )
    with pytest.raises(ValidationError):
        org.full_clean()


@pytest.mark.django_db
def test_vat_validator_accepts_valid() -> None:
    org = Organization(
        name="A",
        slug="a",
        billing_email="a@example.be",
        vat_number="BE0417710407",
    )
    org.full_clean()


@pytest.mark.django_db
def test_vat_validator_rejects_malformed() -> None:
    org = Organization(
        name="A",
        slug="a",
        billing_email="a@example.be",
        vat_number="123",
    )
    with pytest.raises(ValidationError):
        org.full_clean()


@pytest.mark.django_db
def test_slug_validator_rejects_uppercase() -> None:
    org = Organization(name="A", slug="Foo", billing_email="a@example.be")
    with pytest.raises(ValidationError):
        org.full_clean()


@pytest.mark.django_db
def test_country_rejects_unknown_code() -> None:
    org = Organization(
        name="A",
        slug="a",
        billing_email="a@example.be",
        country="ZZ",
    )
    with pytest.raises(ValidationError):
        org.full_clean()


@pytest.mark.django_db
def test_country_rejects_outside_benelux() -> None:
    org = Organization(
        name="A",
        slug="a",
        billing_email="a@example.be",
        country="FR",
    )
    with pytest.raises(ValidationError):
        org.full_clean()


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("code", "vat"),
    [
        ("BE", "BE0417710407"),
        ("NL", "NL000099998B57"),
        ("LU", "LU26375245"),
    ],
)
def test_country_accepts_benelux(code: str, vat: str) -> None:
    org = Organization(
        name="A",
        slug="a",
        billing_email="a@example.be",
        country=code,
        vat_number=vat,
    )
    org.full_clean()


@pytest.mark.django_db
def test_timezone_rejects_unknown() -> None:
    with pytest.raises(ValidationError):
        Organization(
            name="A",
            slug="a",
            billing_email="a@example.be",
            default_timezone="Not/AZone",
        )


@pytest.mark.django_db
def test_locale_rejects_value_outside_enum() -> None:
    org = Organization(
        name="A",
        slug="a",
        billing_email="a@example.be",
        default_language="es",
    )
    with pytest.raises(ValidationError):
        org.full_clean()


@pytest.mark.django_db
def test_currency_rejects_unknown_code() -> None:
    org = Organization(
        name="A",
        slug="a",
        billing_email="a@example.be",
        default_currency="ZZZ",
    )
    with pytest.raises(ValidationError):
        org.full_clean()


@pytest.mark.django_db
def test_vat_validator_rejects_bad_checksum() -> None:
    org = Organization(
        name="A",
        slug="a",
        billing_email="a@example.be",
        vat_number="BE0123456788",
    )
    with pytest.raises(ValidationError):
        org.full_clean()


@pytest.mark.django_db
def test_vat_validator_accepts_valid_nl() -> None:
    org = Organization(
        name="A",
        slug="a",
        billing_email="a@example.nl",
        country="NL",
        vat_number="NL000099998B57",
    )
    org.full_clean()


@pytest.mark.django_db
def test_vat_validator_accepts_valid_lu() -> None:
    org = Organization(
        name="A",
        slug="a",
        billing_email="a@example.lu",
        country="LU",
        vat_number="LU26375245",
    )
    org.full_clean()


@pytest.mark.django_db
def test_vat_validator_rejects_be_for_nl_org() -> None:
    org = Organization(
        name="A",
        slug="a",
        billing_email="a@example.nl",
        country="NL",
        vat_number="BE0417710407",
    )
    with pytest.raises(ValidationError):
        org.full_clean()


@pytest.mark.django_db
def test_vat_validator_rejects_nl_for_be_org() -> None:
    org = Organization(
        name="A",
        slug="a",
        billing_email="a@example.be",
        country="BE",
        vat_number="NL000099998B57",
    )
    with pytest.raises(ValidationError):
        org.full_clean()
