from datetime import timedelta

import jwt

from app.core.security import create_token, decode_token, hash_password, verify_password


def test_password_hash_is_not_reversible_text() -> None:
    password = "UmaSenhaForte123!"
    password_hash = hash_password(password)

    assert password_hash != password
    assert verify_password(password, password_hash)
    assert not verify_password("senha-incorreta", password_hash)


def test_access_token_contains_expected_claims() -> None:
    token = create_token(
        subject=7,
        token_type="access",
        expires_delta=timedelta(minutes=5),
        session_version=0,
    )

    payload = decode_token(token, "access")

    assert payload["sub"] == "7"
    assert payload["type"] == "access"
    assert payload["sv"] == 0


def test_wrong_token_type_is_rejected() -> None:
    token = create_token(
        subject=7,
        token_type="refresh",
        expires_delta=timedelta(minutes=5),
    )

    try:
        decode_token(token, "access")
    except jwt.InvalidTokenError:
        pass
    else:
        raise AssertionError("refresh token was accepted as access token")
