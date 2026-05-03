from datetime import timedelta

import pytest
from django.contrib.auth import (
    BACKEND_SESSION_KEY,
    HASH_SESSION_KEY,
    SESSION_KEY,
)
from django.contrib.sessions.backends.db import SessionStore
from django.contrib.sessions.models import Session
from django.core.exceptions import ValidationError as DjangoValidationError
from django.http import HttpRequest
from django.test import RequestFactory
from django.utils import timezone

from core.models import User
from core.services.exceptions import WeakPasswordError, WrongPasswordError
from core.services.profile import change_password, update_profile
from tests.factories import UserFactory

_CURRENT_PASSWORD = "password"  # UserFactory default
_NEW_PASSWORD = "Hunter2-Strongish!"


def _request_with_session(user: User) -> HttpRequest:
    store = SessionStore()
    store[SESSION_KEY] = str(user.pk)
    store[BACKEND_SESSION_KEY] = "django.contrib.auth.backends.ModelBackend"
    store[HASH_SESSION_KEY] = user.get_session_auth_hash()
    store.create()
    req = RequestFactory().post("/me/password/")
    req.session = store
    req.user = user  # type: ignore[assignment]
    return req


def _create_session_for(user: User) -> Session:
    store = SessionStore()
    store[SESSION_KEY] = str(user.pk)
    store[BACKEND_SESSION_KEY] = "django.contrib.auth.backends.ModelBackend"
    store[HASH_SESSION_KEY] = user.get_session_auth_hash()
    store.create()
    return Session.objects.get(session_key=store.session_key)


# ---- update_profile ---------------------------------------------------------


@pytest.mark.django_db
def test_update_profile_persists_fields() -> None:
    user = UserFactory(first_name="", last_name="", preferred_language="")
    returned = update_profile(
        user,
        first_name="Ada",
        last_name="Lovelace",
        preferred_language="fr-BE",
    )
    user.refresh_from_db()
    assert returned is user
    assert user.first_name == "Ada"
    assert user.last_name == "Lovelace"
    assert user.preferred_language == "fr-BE"


@pytest.mark.django_db
def test_update_profile_allows_blank_language() -> None:
    user = UserFactory(preferred_language="fr-BE")
    update_profile(user, first_name="A", last_name="B", preferred_language="")
    user.refresh_from_db()
    assert user.preferred_language == ""


@pytest.mark.django_db
def test_update_profile_rejects_unknown_language() -> None:
    user = UserFactory(
        first_name="Old", last_name="Name", preferred_language="en-US"
    )
    with pytest.raises(DjangoValidationError):
        update_profile(
            user,
            first_name="New",
            last_name="Name",
            preferred_language="xx-XX",
        )
    user.refresh_from_db()
    assert user.first_name == "Old"
    assert user.preferred_language == "en-US"


# ---- change_password --------------------------------------------------------


@pytest.mark.django_db
def test_change_password_updates_hash() -> None:
    user = UserFactory()
    request = _request_with_session(user)
    change_password(
        request,
        current_password=_CURRENT_PASSWORD,
        new_password=_NEW_PASSWORD,
    )
    user.refresh_from_db()
    assert user.check_password(_NEW_PASSWORD)
    assert not user.check_password(_CURRENT_PASSWORD)


@pytest.mark.django_db
def test_change_password_wrong_current_raises() -> None:
    user = UserFactory()
    original_hash = user.password
    request = _request_with_session(user)
    with pytest.raises(WrongPasswordError):
        change_password(
            request,
            current_password="not-the-password",
            new_password=_NEW_PASSWORD,
        )
    user.refresh_from_db()
    assert user.password == original_hash


@pytest.mark.django_db
def test_change_password_weak_new_raises() -> None:
    user = UserFactory()
    original_hash = user.password
    request = _request_with_session(user)
    with pytest.raises(WeakPasswordError):
        change_password(
            request,
            current_password=_CURRENT_PASSWORD,
            new_password="123",
        )
    user.refresh_from_db()
    assert user.password == original_hash


@pytest.mark.django_db
def test_change_password_keeps_current_session() -> None:
    user = UserFactory()
    request = _request_with_session(user)
    change_password(
        request,
        current_password=_CURRENT_PASSWORD,
        new_password=_NEW_PASSWORD,
    )
    user.refresh_from_db()
    request.session.save()
    session = Session.objects.get(session_key=request.session.session_key)
    decoded = session.get_decoded()
    assert decoded[SESSION_KEY] == str(user.pk)
    assert decoded[HASH_SESSION_KEY] == user.get_session_auth_hash()


@pytest.mark.django_db
def test_change_password_invalidates_other_sessions() -> None:
    user = UserFactory()
    other_session = _create_session_for(user)
    request = _request_with_session(user)
    change_password(
        request,
        current_password=_CURRENT_PASSWORD,
        new_password=_NEW_PASSWORD,
    )
    assert not Session.objects.filter(
        session_key=other_session.session_key
    ).exists()
    assert Session.objects.filter(
        session_key=request.session.session_key
    ).exists()


@pytest.mark.django_db
def test_change_password_leaves_other_users_sessions_alone() -> None:
    user = UserFactory()
    other_user = UserFactory()
    other_user_session = _create_session_for(other_user)
    request = _request_with_session(user)
    change_password(
        request,
        current_password=_CURRENT_PASSWORD,
        new_password=_NEW_PASSWORD,
    )
    assert Session.objects.filter(
        session_key=other_user_session.session_key
    ).exists()


@pytest.mark.django_db
def test_change_password_skips_expired_sessions() -> None:
    user = UserFactory()
    expired = _create_session_for(user)
    expired.expire_date = timezone.now() - timedelta(days=1)
    expired.save(update_fields=["expire_date"])
    request = _request_with_session(user)
    change_password(
        request,
        current_password=_CURRENT_PASSWORD,
        new_password=_NEW_PASSWORD,
    )
    assert Session.objects.filter(session_key=expired.session_key).exists()
