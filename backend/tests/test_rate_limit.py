"""
app/core/rate_limit.py: the core Redis fixed-window primitive
(check_and_consume), fail-open behavior when Redis is unavailable/errors,
and the 429 response shape end-to-end through a real endpoint.
"""

import uuid
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import fakeredis
import pytest
from fastapi.testclient import TestClient
from redis.exceptions import RedisError

from app.core import rate_limit
from app.core.config import settings
from app.core.database import get_db
from app.dependencies.auth import get_current_profile
from app.main import app
from tests.conftest import DEFAULT_TEST_USER_ID, make_token

client = TestClient(app)
API = settings.API_V1_STR


@pytest.fixture
def fake_redis():
    return fakeredis.FakeAsyncRedis(decode_responses=True)


@pytest.fixture(autouse=True)
def _rate_limit_enabled(monkeypatch):
    monkeypatch.setattr(settings, "RATE_LIMIT_ENABLED", True)


# ---- check_and_consume: the core primitive ---------------------------------


async def test_first_request_under_limit_is_allowed(fake_redis):
    allowed, retry_after = await rate_limit.check_and_consume(fake_redis, "test", "user:1", limit=3, window_seconds=60)
    assert allowed is True
    assert retry_after == 0


async def test_requests_up_to_the_limit_are_all_allowed(fake_redis):
    for _ in range(3):
        allowed, _ = await rate_limit.check_and_consume(fake_redis, "test", "user:1", limit=3, window_seconds=60)
        assert allowed is True


async def test_request_over_the_limit_is_rejected(fake_redis):
    for _ in range(3):
        await rate_limit.check_and_consume(fake_redis, "test", "user:1", limit=3, window_seconds=60)
    allowed, retry_after = await rate_limit.check_and_consume(fake_redis, "test", "user:1", limit=3, window_seconds=60)
    assert allowed is False
    assert retry_after > 0


async def test_retry_after_reflects_remaining_window(fake_redis):
    await rate_limit.check_and_consume(fake_redis, "test", "user:1", limit=1, window_seconds=60)
    allowed, retry_after = await rate_limit.check_and_consume(fake_redis, "test", "user:1", limit=1, window_seconds=60)
    assert allowed is False
    assert 1 <= retry_after <= 60


async def test_different_identifiers_have_independent_buckets(fake_redis):
    await rate_limit.check_and_consume(fake_redis, "test", "user:1", limit=1, window_seconds=60)
    allowed, _ = await rate_limit.check_and_consume(fake_redis, "test", "user:2", limit=1, window_seconds=60)
    assert allowed is True  # user:2's own bucket is untouched by user:1's usage


async def test_different_scopes_have_independent_buckets(fake_redis):
    await rate_limit.check_and_consume(fake_redis, "scope_a", "user:1", limit=1, window_seconds=60)
    allowed, _ = await rate_limit.check_and_consume(fake_redis, "scope_b", "user:1", limit=1, window_seconds=60)
    assert allowed is True


async def test_redis_error_fails_open(fake_redis, monkeypatch):
    """A Redis error mid-check must never block real traffic — see the
    module docstring's "fails OPEN, not closed" rule."""

    async def _boom(*args, **kwargs):
        raise RedisError("simulated failure")

    monkeypatch.setattr(fake_redis, "incr", _boom)
    allowed, retry_after = await rate_limit.check_and_consume(fake_redis, "test", "user:1", limit=1, window_seconds=60)
    assert allowed is True
    assert retry_after == 0


# ---- disabled / unconfigured Redis -----------------------------------------


async def test_disabled_rate_limiting_never_blocks(monkeypatch):
    monkeypatch.setattr(settings, "RATE_LIMIT_ENABLED", False)
    # _enforce should return immediately without ever touching Redis.
    await rate_limit._enforce("test", "user:1", limit_per_minute=0, window_seconds=60)


# ---- end-to-end through a real endpoint (join-group) -----------------------


@pytest.fixture
def fake_profile_override():
    """Same pattern as test_groups_api.py — a fake authenticated profile
    and a mocked DB session, so the endpoint under test never needs a
    real Postgres connection."""
    fake_profile = SimpleNamespace(id=uuid.UUID(DEFAULT_TEST_USER_ID), full_name="Test User", avatar_url=None)
    app.dependency_overrides[get_current_profile] = lambda: fake_profile
    app.dependency_overrides[get_db] = lambda: MagicMock()
    yield fake_profile
    app.dependency_overrides.pop(get_current_profile, None)
    app.dependency_overrides.pop(get_db, None)


@patch("app.api.groups.group_service.join_group")
def test_join_group_returns_429_with_standard_envelope_once_limit_exceeded(mock_join, fake_profile_override, monkeypatch):
    monkeypatch.setattr(settings, "JOIN_GROUP_RATE_LIMIT_PER_MINUTE", 1)
    # Both the join-group-specific limiter (_enforce) and the general
    # per-request middleware limiter (GeneralRateLimitMiddleware) call the
    # `get_redis` name bound into this same module at import time — one
    # patch target covers both, and the much higher general limit never
    # itself trips within this test's two requests.
    shared = fakeredis.FakeAsyncRedis(decode_responses=True)
    monkeypatch.setattr("app.core.rate_limit.get_redis", lambda: shared)

    mock_group = MagicMock()
    mock_group.id = uuid.uuid4()
    mock_group.name = "Test Group"
    mock_group.join_code = "RALLY-12345"
    mock_group.leader_id = uuid.uuid4()
    mock_group.destination_name = None
    mock_group.status = "ACTIVE"
    mock_group.created_at = "2026-08-25T00:00:00Z"
    mock_group.updated_at = "2026-08-25T00:00:00Z"
    mock_join.return_value = mock_group

    token = make_token(sub=DEFAULT_TEST_USER_ID)
    headers = {"Authorization": f"Bearer {token}"}
    body = {"join_code": "ABCDEF"}

    first = client.post(f"{API}/groups/join", headers=headers, json=body)
    assert first.status_code == 200

    second = client.post(f"{API}/groups/join", headers=headers, json=body)

    assert second.status_code == 429
    response_body = second.json()
    assert response_body["success"] is False
    assert response_body["error"]["code"] == "RATE_LIMITED"
    assert response_body["error"]["retry_after_seconds"] >= 1
    assert "request_id" in response_body["error"]
    assert "Retry-After" in second.headers
