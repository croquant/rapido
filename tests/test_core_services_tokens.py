import pytest
from django.core.signing import BadSignature, SignatureExpired

from core.services.tokens import (
    INVITE_SALT,
    RESET_MAX_AGE,
    RESET_SALT,
    VERIFY_MAX_AGE,
    VERIFY_SALT,
    make_token,
    verify_token,
)
from tests.factories import UserFactory


@pytest.mark.django_db
def test_round_trip_returns_user_id() -> None:
    user = UserFactory()
    token = make_token(user, salt=VERIFY_SALT)
    payload = verify_token(token, salt=VERIFY_SALT, max_age=VERIFY_MAX_AGE)
    assert payload == {"user_id": user.pk}


@pytest.mark.django_db
def test_tampered_token_raises_bad_signature() -> None:
    user = UserFactory()
    token = make_token(user, salt=VERIFY_SALT)
    tampered = token[:-1] + ("A" if token[-1] != "A" else "B")
    with pytest.raises(BadSignature):
        verify_token(tampered, salt=VERIFY_SALT, max_age=VERIFY_MAX_AGE)


@pytest.mark.django_db
def test_expired_token_raises_signature_expired() -> None:
    user = UserFactory()
    token = make_token(user, salt=RESET_SALT)
    with pytest.raises(SignatureExpired):
        verify_token(token, salt=RESET_SALT, max_age=-1)


@pytest.mark.django_db
def test_cross_salt_reuse_rejected() -> None:
    user = UserFactory()
    token = make_token(user, salt=VERIFY_SALT)
    with pytest.raises(BadSignature):
        verify_token(token, salt=RESET_SALT, max_age=RESET_MAX_AGE)


def test_salt_constants_are_locked() -> None:
    assert VERIFY_SALT == "verify-email"
    assert RESET_SALT == "password-reset"
    assert INVITE_SALT == "invite"
