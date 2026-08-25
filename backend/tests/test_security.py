import pytest

from app.core.security import (
    InvalidTokenError,
    decode_supabase_jwt,
    extract_profile_hints,
    get_user_id_from_token,
)
from tests.conftest import DEFAULT_TEST_USER_ID, make_token


def test_decode_valid_token_returns_claims():
    token = make_token(sub=DEFAULT_TEST_USER_ID, email="a@b.com")
    claims = decode_supabase_jwt(token)
    assert claims["sub"] == DEFAULT_TEST_USER_ID
    assert claims["email"] == "a@b.com"


def test_get_user_id_from_token():
    token = make_token(sub=DEFAULT_TEST_USER_ID)
    assert get_user_id_from_token(token) == DEFAULT_TEST_USER_ID


def test_expired_token_is_rejected():
    token = make_token(expires_in_seconds=-10)
    with pytest.raises(InvalidTokenError):
        decode_supabase_jwt(token)


def test_wrong_signing_secret_is_rejected():
    token = make_token(secret="a-completely-different-secret")
    with pytest.raises(InvalidTokenError):
        decode_supabase_jwt(token)


def test_wrong_audience_is_rejected():
    token = make_token(audience="something-else")
    with pytest.raises(InvalidTokenError):
        decode_supabase_jwt(token)


def test_missing_audience_is_rejected():
    token = make_token(audience=None)
    with pytest.raises(InvalidTokenError):
        decode_supabase_jwt(token)


def test_malformed_token_is_rejected():
    with pytest.raises(InvalidTokenError):
        decode_supabase_jwt("this-is-not-a-jwt")


def test_missing_jwt_secret_config_is_rejected(monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, "JWT_SECRET", None)
    token = make_token()
    with pytest.raises(InvalidTokenError):
        decode_supabase_jwt(token)


def test_issuer_is_verified_when_supabase_url_configured(monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, "SUPABASE_URL", "https://myproject.supabase.co")
    # Token has no iss claim at all, so it must fail once an issuer is required.
    token = make_token()
    with pytest.raises(InvalidTokenError):
        decode_supabase_jwt(token)


def test_extract_profile_hints_reads_user_metadata():
    claims = {"user_metadata": {"full_name": "Ada Lovelace", "avatar_url": "https://x/y.png"}}
    full_name, avatar_url = extract_profile_hints(claims)
    assert full_name == "Ada Lovelace"
    assert avatar_url == "https://x/y.png"


def test_extract_profile_hints_falls_back_to_name_and_picture():
    claims = {"user_metadata": {"name": "Grace Hopper", "picture": "https://x/z.png"}}
    full_name, avatar_url = extract_profile_hints(claims)
    assert full_name == "Grace Hopper"
    assert avatar_url == "https://x/z.png"


def test_extract_profile_hints_handles_missing_metadata():
    assert extract_profile_hints({}) == (None, None)
    assert extract_profile_hints({"user_metadata": None}) == (None, None)
