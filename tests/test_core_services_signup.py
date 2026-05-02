from typing import Any
from unittest.mock import patch

import pytest
from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction

from core.models import Organization, OrganizationMembership, Role, User
from core.services.signup import create_organization_with_admin

_Capture = Any


@pytest.mark.django_db
def test_creates_all_three_rows() -> None:
    org, user, mem = create_organization_with_admin(
        email="o@x.be",
        password="hunter22",
        org_name="X",
        org_slug="x",
        vat_number="BE0417710407",
        billing_email="b@x.be",
        default_language="en-US",
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
        default_language="en-US",
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
        default_language="en-US",
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
        default_language="en-US",
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
            default_language="en-US",
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
        default_language="en-US",
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
            default_language="en-US",
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
            default_language="en-US",
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
            default_language="en-US",
        )


@pytest.mark.django_db
def test_default_language_persisted_on_org_and_user() -> None:
    org, user, _ = create_organization_with_admin(
        email="o@x.be",
        password="hunter22",
        org_name="X",
        org_slug="x",
        vat_number="BE0417710407",
        billing_email="b@x.be",
        default_language="nl-BE",
    )
    org.refresh_from_db()
    user.refresh_from_db()
    assert org.default_language == "nl-BE"
    assert user.preferred_language == "nl-BE"


@pytest.mark.django_db
def test_verify_email_enqueued_on_commit(
    django_capture_on_commit_callbacks: _Capture,
) -> None:
    with patch("core.services.signup.send_templated") as send:
        with django_capture_on_commit_callbacks(execute=True) as callbacks:
            _, user, _ = create_organization_with_admin(
                email="o@x.be",
                password="hunter22",
                org_name="X",
                org_slug="x",
                vat_number="BE0417710407",
                billing_email="b@x.be",
                default_language="nl-BE",
            )
        assert len(callbacks) == 1
        send.assert_called_once()
        args, kwargs = send.call_args
        assert args == ("email/verify",)
        assert kwargs["to"] == user
        assert kwargs["language"] == "nl-BE"
        assert kwargs["context"]["org_name"] == "X"
        assert kwargs["context"]["verify_url"].startswith(
            f"{settings.SITE_URL}/verify/"
        )


@pytest.mark.django_db
def test_email_send_failure_does_not_break_signup(
    django_capture_on_commit_callbacks: _Capture,
    caplog: pytest.LogCaptureFixture,
) -> None:
    with (
        patch(
            "core.services.signup.send_templated",
            side_effect=RuntimeError("smtp down"),
        ),
        django_capture_on_commit_callbacks(execute=True),
    ):
        org, user, _ = create_organization_with_admin(
            email="o@x.be",
            password="hunter22",
            org_name="X",
            org_slug="x",
            vat_number="BE0417710407",
            billing_email="b@x.be",
            default_language="nl-BE",
        )
    assert org.pk is not None
    assert user.pk is not None
    assert any("verify email send failed" in r.message for r in caplog.records)


@pytest.mark.django_db
def test_email_not_sent_if_transaction_rolls_back(
    django_capture_on_commit_callbacks: _Capture,
) -> None:
    with (
        patch("core.services.signup.send_templated") as send,
        django_capture_on_commit_callbacks(execute=True),
        pytest.raises(RuntimeError),
        transaction.atomic(),
    ):
        create_organization_with_admin(
            email="o@x.be",
            password="hunter22",
            org_name="X",
            org_slug="x",
            vat_number="BE0417710407",
            billing_email="b@x.be",
            default_language="nl-BE",
        )
        raise RuntimeError("force rollback")
    send.assert_not_called()
