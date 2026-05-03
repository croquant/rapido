import pytest
from django.contrib.auth import (
    BACKEND_SESSION_KEY,
    HASH_SESSION_KEY,
    SESSION_KEY,
)
from django.contrib.sessions.backends.db import SessionStore
from django.contrib.sessions.models import Session
from django.test import Client

from core.models import User
from tests.factories import UserFactory

ME_URL = "/me/"
PROFILE_URL = "/me/profile/"
PASSWORD_URL = "/me/password/"

CURRENT_PASSWORD = "password"  # UserFactory default
NEW_PASSWORD = "Hunter2-Strongish!"


def _create_db_session_for(user: User) -> Session:
    store = SessionStore()
    store[SESSION_KEY] = str(user.pk)
    store[BACKEND_SESSION_KEY] = "django.contrib.auth.backends.ModelBackend"
    store[HASH_SESSION_KEY] = user.get_session_auth_hash()
    store.create()
    return Session.objects.get(session_key=store.session_key)


# ---- anonymous --------------------------------------------------------------


@pytest.mark.django_db
def test_anonymous_redirects_to_login() -> None:
    response = Client().get(ME_URL)
    assert response.status_code == 302
    assert response["Location"] == f"/login/?next={ME_URL}"


# ---- GET /me/ ---------------------------------------------------------------


@pytest.mark.django_db
def test_authenticated_get_renders_both_forms() -> None:
    user = UserFactory()
    client = Client()
    client.force_login(user)

    response = client.get(ME_URL)

    assert response.status_code == 200
    body = response.content.decode()
    assert f'action="{PROFILE_URL}"' in body
    assert f'action="{PASSWORD_URL}"' in body
    assert 'name="first_name"' in body
    assert 'name="preferred_language"' in body
    assert 'name="current_password"' in body
    assert 'name="new_password1"' in body
    assert 'name="new_password2"' in body


@pytest.mark.django_db
def test_me_works_without_org_context() -> None:
    # Newly invited user with no memberships should still be able to reach /me/.
    user = UserFactory()
    client = Client()
    client.force_login(user)

    response = client.get(ME_URL)

    assert response.status_code == 200


# ---- POST /me/profile/ ------------------------------------------------------


@pytest.mark.django_db
def test_post_profile_updates_fields_and_redirects() -> None:
    user = UserFactory(first_name="", last_name="", preferred_language="")
    client = Client()
    client.force_login(user)

    response = client.post(
        PROFILE_URL,
        {
            "first_name": "Ada",
            "last_name": "Lovelace",
            "preferred_language": "fr-BE",
        },
    )

    assert response.status_code == 302
    assert response["Location"] == ME_URL
    user.refresh_from_db()
    assert user.first_name == "Ada"
    assert user.last_name == "Lovelace"
    assert user.preferred_language == "fr-BE"


@pytest.mark.django_db
def test_post_profile_blank_language_clears_field() -> None:
    user = UserFactory(preferred_language="fr-BE")
    client = Client()
    client.force_login(user)

    response = client.post(
        PROFILE_URL,
        {
            "first_name": "A",
            "last_name": "B",
            "preferred_language": "",
        },
    )

    assert response.status_code == 302
    user.refresh_from_db()
    assert user.preferred_language == ""


@pytest.mark.django_db
def test_post_profile_unknown_language_renders_error() -> None:
    user = UserFactory(preferred_language="en-US")
    client = Client()
    client.force_login(user)

    response = client.post(
        PROFILE_URL,
        {
            "first_name": "A",
            "last_name": "B",
            "preferred_language": "xx-XX",
        },
    )

    assert response.status_code == 200
    form = response.context["profile_form"]
    assert "preferred_language" in form.errors
    user.refresh_from_db()
    assert user.preferred_language == "en-US"


@pytest.mark.django_db
def test_get_only_routes_reject_get() -> None:
    user = UserFactory()
    client = Client()
    client.force_login(user)

    assert client.get(PROFILE_URL).status_code == 405
    assert client.get(PASSWORD_URL).status_code == 405


# ---- POST /me/password/ -----------------------------------------------------


@pytest.mark.django_db
def test_post_password_wrong_current_renders_error() -> None:
    user = UserFactory()
    original_hash = user.password
    client = Client()
    client.force_login(user)

    response = client.post(
        PASSWORD_URL,
        {
            "current_password": "not-the-password",
            "new_password1": NEW_PASSWORD,
            "new_password2": NEW_PASSWORD,
        },
    )

    assert response.status_code == 200
    form = response.context["password_form"]
    assert "current_password" in form.errors
    user.refresh_from_db()
    assert user.password == original_hash


@pytest.mark.django_db
def test_post_password_mismatch_renders_error() -> None:
    user = UserFactory()
    original_hash = user.password
    client = Client()
    client.force_login(user)

    response = client.post(
        PASSWORD_URL,
        {
            "current_password": CURRENT_PASSWORD,
            "new_password1": NEW_PASSWORD,
            "new_password2": NEW_PASSWORD + "x",
        },
    )

    assert response.status_code == 200
    form = response.context["password_form"]
    assert "new_password2" in form.errors
    user.refresh_from_db()
    assert user.password == original_hash


@pytest.mark.django_db
def test_post_password_weak_renders_error() -> None:
    user = UserFactory()
    original_hash = user.password
    client = Client()
    client.force_login(user)

    response = client.post(
        PASSWORD_URL,
        {
            "current_password": CURRENT_PASSWORD,
            "new_password1": "123",
            "new_password2": "123",
        },
    )

    assert response.status_code == 200
    form = response.context["password_form"]
    assert "new_password1" in form.errors
    user.refresh_from_db()
    assert user.password == original_hash


@pytest.mark.django_db
def test_post_password_success_keeps_current_session_and_invalidates_others() -> (
    None
):
    user = UserFactory()
    other_session = _create_db_session_for(user)
    client = Client()
    client.force_login(user)

    response = client.post(
        PASSWORD_URL,
        {
            "current_password": CURRENT_PASSWORD,
            "new_password1": NEW_PASSWORD,
            "new_password2": NEW_PASSWORD,
        },
    )

    assert response.status_code == 302
    assert response["Location"] == ME_URL

    # Current session still authenticated: a follow-up authenticated GET works.
    follow_up = client.get(ME_URL)
    assert follow_up.status_code == 200

    # The other session for the same user has been deleted.
    assert not Session.objects.filter(
        session_key=other_session.session_key
    ).exists()

    user.refresh_from_db()
    assert user.check_password(NEW_PASSWORD)


@pytest.mark.django_db
def test_post_password_success_leaves_other_users_sessions_alone() -> None:
    user = UserFactory()
    other_user = UserFactory()
    other_user_session = _create_db_session_for(other_user)
    client = Client()
    client.force_login(user)

    response = client.post(
        PASSWORD_URL,
        {
            "current_password": CURRENT_PASSWORD,
            "new_password1": NEW_PASSWORD,
            "new_password2": NEW_PASSWORD,
        },
    )

    assert response.status_code == 302
    assert Session.objects.filter(
        session_key=other_user_session.session_key
    ).exists()
