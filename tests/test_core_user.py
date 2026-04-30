import uuid

import pytest
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import IntegrityError

from core.models import User


def test_user_str_returns_email() -> None:
    user = User(email="x@example.be")
    assert str(user) == "x@example.be"


def test_user_username_field_is_email() -> None:
    assert User.USERNAME_FIELD == "email"


def test_user_required_fields_empty() -> None:
    assert User.REQUIRED_FIELDS == []


def test_get_user_model_returns_core_user() -> None:
    assert get_user_model() is User


@pytest.mark.django_db
def test_create_user_normalizes_email_lowercase() -> None:
    user = User.objects.create_user(email="Foo@Example.BE", password="pw")
    assert user.email == "foo@example.be"


@pytest.mark.django_db
def test_create_user_requires_email() -> None:
    with pytest.raises(ValueError, match="email"):
        User.objects.create_user(email="", password="pw")


@pytest.mark.django_db
def test_create_user_hashes_password() -> None:
    user = User.objects.create_user(email="a@example.be", password="raw-pw")
    assert user.password != "raw-pw"
    assert user.check_password("raw-pw") is True


@pytest.mark.django_db
def test_email_unique_case_sensitive() -> None:
    User.objects.create_user(email="a@example.be", password="pw")
    with pytest.raises(IntegrityError):
        User.objects.create_user(email="a@example.be", password="pw")


@pytest.mark.django_db
def test_email_unique_case_insensitive() -> None:
    User.objects.create_user(email="foo@example.be", password="pw")
    with pytest.raises(IntegrityError):
        User.objects.create(email="Foo@Example.BE", password="pw")


@pytest.mark.django_db
def test_user_public_id_is_uuid7() -> None:
    user = User.objects.create_user(email="a@example.be", password="pw")
    assert isinstance(user.public_id, uuid.UUID)
    assert user.public_id.version == 7


@pytest.mark.django_db
def test_user_preferred_language_blank_ok() -> None:
    user = User(email="a@example.be", password="pw", preferred_language="")
    user.full_clean()


@pytest.mark.django_db
def test_user_preferred_language_rejects_unknown() -> None:
    user = User(email="a@example.be", password="pw", preferred_language="es")
    with pytest.raises(ValidationError):
        user.full_clean()


@pytest.mark.django_db
def test_user_inherits_timestamps() -> None:
    user = User.objects.create_user(email="a@example.be", password="pw")
    assert user.created_at is not None
    assert user.updated_at is not None


@pytest.mark.django_db
def test_create_superuser_sets_flags() -> None:
    user = User.objects.create_superuser(
        email="a@example.be", password="pw"
    )
    assert user.is_staff is True
    assert user.is_superuser is True
    assert user.is_active is True


@pytest.mark.django_db
def test_create_superuser_rejects_non_staff() -> None:
    with pytest.raises(ValueError, match="is_staff"):
        User.objects.create_superuser(
            email="a@example.be", password="pw", is_staff=False
        )


@pytest.mark.django_db
def test_create_superuser_rejects_non_superuser() -> None:
    with pytest.raises(ValueError, match="is_superuser"):
        User.objects.create_superuser(
            email="a@example.be", password="pw", is_superuser=False
        )
