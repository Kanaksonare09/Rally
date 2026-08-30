"""
app/core/redis.py's own lifecycle functions — these must degrade
gracefully (never raise) on missing/malformed configuration, since a
Redis problem must never take down the database-backed REST API.
"""

from app.core import redis as redis_core


def test_init_redis_with_no_url_configured(monkeypatch):
    monkeypatch.setattr(redis_core.settings, "REDIS_URL", None)
    redis_core._client = "sentinel"  # prove init_redis() actually resets this

    redis_core.init_redis()

    assert redis_core._client is None


def test_init_redis_with_malformed_url_does_not_raise(monkeypatch):
    """A real bug this project hit: REDIS_URL set to something without a
    redis://-family scheme (e.g. a provider's REST URL pasted in by
    mistake) previously crashed the whole app at startup."""
    monkeypatch.setattr(redis_core.settings, "REDIS_URL", "https://example-provider.io/not-a-redis-url")

    redis_core.init_redis()  # must not raise

    assert redis_core._client is None


def test_init_redis_with_valid_url_builds_a_client(monkeypatch):
    monkeypatch.setattr(redis_core.settings, "REDIS_URL", "redis://localhost:6379/0")

    redis_core.init_redis()

    assert redis_core._client is not None
    redis_core._client = None  # don't leak a real client into other tests


def test_get_redis_raises_runtime_error_when_not_configured(monkeypatch):
    import pytest

    redis_core._client = None
    with pytest.raises(RuntimeError):
        redis_core.get_redis()


async def test_ping_redis_returns_false_when_not_configured():
    redis_core._client = None
    assert await redis_core.ping_redis() is False
