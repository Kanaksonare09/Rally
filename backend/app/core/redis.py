"""
Async Redis client lifecycle. Redis here is exclusively LIVE/TEMPORARY
state — current location, presence, pub/sub — never the permanent record
of anything. See app/core/redis_keys.py for the key namespace and the
backend README's "Redis vs Supabase" section for the full split.

One client is created at app startup and reused for the life of the
process (never build a new client per request/message — see the
`app/websocket/` layer, which always calls get_redis()). Every call here
is async (redis.asyncio), so it's safe to await directly from WebSocket
handlers without blocking the event loop.
"""

import logging
from typing import Optional

import redis.asyncio as redis
from redis.asyncio import Redis
from redis.exceptions import RedisError

from app.core.config import settings

logger = logging.getLogger("rally.redis")

_client: Optional[Redis] = None


def init_redis() -> None:
    """Call once during app startup. Building the client doesn't connect
    yet (redis-py connects lazily on first command) — call ping_redis() if
    you need to confirm connectivity up front.

    Must never raise: a malformed REDIS_URL (wrong scheme, typo, a
    provider's REST URL pasted in by mistake) is exactly the kind of
    misconfiguration that should degrade to "Redis unavailable" — same as
    an unreachable host — not crash the entire application on startup and
    take the database-backed REST API down with it."""
    global _client
    if not settings.REDIS_URL:
        logger.warning("REDIS_URL is not set - live tracking (WebSockets) will be unavailable.")
        _client = None
        return
    try:
        _client = redis.from_url(
            settings.REDIS_URL,
            decode_responses=True,
            # Part 5 — Redis resilience: no command may hang indefinitely.
            # A slow/half-open connection fails within these bounds
            # instead of blocking the request (or the intelligence
            # worker's tick) forever.
            socket_connect_timeout=settings.REDIS_CONNECT_TIMEOUT_SECONDS,
            socket_timeout=settings.REDIS_SOCKET_TIMEOUT_SECONDS,
            retry_on_timeout=True,
            health_check_interval=30,
        )
    except Exception as exc:
        logger.error(
            "REDIS_URL is set but invalid (%s) - live tracking (WebSockets) will be unavailable.",
            exc.__class__.__name__,
        )
        _client = None


async def close_redis() -> None:
    """Call once during app shutdown. Safe to call even if init_redis()
    was never called or Redis was never configured."""
    global _client
    if _client is not None:
        await _client.aclose()
        _client = None


def get_redis() -> Redis:
    """Returns the shared client. Raises RuntimeError if Redis isn't
    configured — callers (WebSocket routes, live_state_service,
    presence_service) must turn that into a clean user-facing error, never
    let it surface as a raw 500/stack trace."""
    if _client is None:
        raise RuntimeError("Redis is not configured. Set REDIS_URL in your environment.")
    return _client


async def ping_redis() -> bool:
    """Used by /health — never raises, just reports reachability."""
    if _client is None:
        return False
    try:
        return bool(await _client.ping())
    except RedisError as exc:
        logger.error("Redis health check failed: %s", exc)
        return False
