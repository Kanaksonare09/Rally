import time
from typing import Optional

import fakeredis
import jwt
import pytest

from app.core.config import settings

TEST_JWT_SECRET = "test-only-secret-do-not-use-in-production"
DEFAULT_TEST_USER_ID = "11111111-1111-1111-1111-111111111111"


@pytest.fixture
def fake_redis():
    """A fresh in-memory Redis per test — no real Redis server required
    (see backend README). `decode_responses=True` matches the real client
    built in app/core/redis.py, so values round-trip as str, not bytes."""
    client = fakeredis.FakeAsyncRedis(decode_responses=True)
    yield client


@pytest.fixture(autouse=True)
def configured_jwt_secret(monkeypatch):
    """Every test runs with a known JWT_SECRET so tokens crafted with
    make_token() below verify successfully, without needing a real
    Supabase project. Also pins SUPABASE_URL to None so the suite doesn't
    depend on whatever a real local .env happens to contain — a developer's
    real .env commonly sets SUPABASE_URL, which would otherwise force
    issuer verification on every test even though make_token() doesn't set
    an `iss` claim by default (see test_issuer_is_verified_when_supabase_url_configured
    for the one test that opts back in). monkeypatch auto-reverts after
    each test."""
    monkeypatch.setattr(settings, "JWT_SECRET", TEST_JWT_SECRET)
    monkeypatch.setattr(settings, "SUPABASE_URL", None)
    yield


def make_token(
    sub: str = DEFAULT_TEST_USER_ID,
    email: Optional[str] = "demo@rally.app",
    expires_in_seconds: int = 3600,
    secret: str = TEST_JWT_SECRET,
    audience: Optional[str] = "authenticated",
    user_metadata: Optional[dict] = None,
    algorithm: str = "HS256",
) -> str:
    """Builds a Supabase-shaped JWT signed with `secret`. Use a different
    secret/audience/expiry to construct invalid tokens for negative tests."""
    now = int(time.time())
    payload = {
        "sub": sub,
        "email": email,
        "iat": now,
        "exp": now + expires_in_seconds,
        "user_metadata": user_metadata or {},
    }
    if audience is not None:
        payload["aud"] = audience
    return jwt.encode(payload, secret, algorithm=algorithm)
