import pytest
from django.core.exceptions import ValidationError
from django.db import IntegrityError

from core.models import Organization, OrganizationMembership, Role, User
from core.services.signup import create_organization_with_admin


@pytest.mark.django_db
def test_creates_all_three_rows() -> None:
    org, user, mem = create_organization_with_admin(
        email="o@x.be",
        password="hunter22",
        org_name="X",
        org_slug="x",
        vat_number="BE0417710407",
        billing_email="b@x.be",
    )
    assert org.is_active is False
    assert user.is_active is False
    assert mem.role == Role.ADMIN
    assert mem.is_active is True
    assert mem.created_by is None
    assert user.check_password("hunter22")


@pytest.mark.django_db
def test_normalizes_email_to_lowercase() -> None:
    _, user, _ = create_organization_with_admin(
        email="Foo@Example.BE",
        password="hunter22",
        org_name="X",
        org_slug="x",
        vat_number="BE0417710407",
        billing_email="b@x.be",
    )
    assert user.email == "foo@example.be"


@pytest.mark.django_db
def test_returns_three_tuple_of_correct_types() -> None:
    result = create_organization_with_admin(
        email="o@x.be",
        password="hunter22",
        org_name="X",
        org_slug="x",
        vat_number="BE0417710407",
        billing_email="b@x.be",
    )
    assert isinstance(result, tuple)
    assert len(result) == 3
    assert isinstance(result[0], Organization)
    assert isinstance(result[1], User)
    assert isinstance(result[2], OrganizationMembership)


@pytest.mark.django_db
def test_duplicate_slug_raises_integrity_error_no_partial_rows() -> None:
    create_organization_with_admin(
        email="a@x.be",
        password="hunter22",
        org_name="X1",
        org_slug="x",
        vat_number="BE0417710407",
        billing_email="b@x.be",
    )
    org_count = Organization.objects.count()
    user_count = User.objects.count()
    mem_count = OrganizationMembership.objects.count()
    with pytest.raises(IntegrityError):
        create_organization_with_admin(
            email="b@x.be",
            password="hunter22",
            org_name="X2",
            org_slug="x",
            vat_number="BE0417710407",
            billing_email="b@x.be",
        )
    assert Organization.objects.count() == org_count
    assert User.objects.count() == user_count
    assert OrganizationMembership.objects.count() == mem_count


@pytest.mark.django_db
def test_duplicate_email_raises_integrity_error_no_partial_rows() -> None:
    create_organization_with_admin(
        email="a@x.be",
        password="hunter22",
        org_name="X1",
        org_slug="x1",
        vat_number="BE0417710407",
        billing_email="b@x.be",
    )
    org_count = Organization.objects.count()
    user_count = User.objects.count()
    mem_count = OrganizationMembership.objects.count()
    with pytest.raises(IntegrityError):
        create_organization_with_admin(
            email="A@X.BE",
            password="hunter22",
            org_name="X2",
            org_slug="x2",
            vat_number="BE0417710407",
            billing_email="b@x.be",
        )
    assert Organization.objects.count() == org_count
    assert User.objects.count() == user_count
    assert OrganizationMembership.objects.count() == mem_count


@pytest.mark.django_db
def test_invalid_slug_raises_validation_error() -> None:
    with pytest.raises(ValidationError):
        create_organization_with_admin(
            email="o@x.be",
            password="hunter22",
            org_name="X",
            org_slug="NotASlug!",
            vat_number="BE0417710407",
            billing_email="b@x.be",
        )


@pytest.mark.django_db
def test_vat_country_mismatch_raises_validation_error() -> None:
    with pytest.raises(ValidationError):
        create_organization_with_admin(
            email="o@x.be",
            password="hunter22",
            org_name="X",
            org_slug="x",
            vat_number="FR12345678901",
            billing_email="b@x.be",
            country="BE",
        )
