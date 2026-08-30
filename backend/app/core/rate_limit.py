"""
Redis-backed API rate limiting (Part 3). Fixed-window counters —
`INCR` + `EXPIRE` on first increment — rather than a sliding-window log:
simple, O(1) per check, and accurate enough for the limits this phase
actually needs (tens to low-hundreds of requests per minute, not
precision traffic shaping).

Key shape: `rate_limit:{scope}:{identifier}` — `identifier` is
`user:{user_id}` for an authenticated caller, `ip:{client_ip}` otherwise
(never both at once, and never anything else — no email, no join code, no
request path). See app/core/redis_keys.py for every other key namespace
this project uses; rate-limit keys live here instead since they're this
module's own concern, not shared with any other service.

Fails OPEN, not closed: if Redis is unreachable or unconfigured, every
check here allows the request rather than blocking it. Rate limiting is a
best-effort abuse guard, not a safety-critical control — a Redis outage
must never turn into "the whole API stops responding," which is exactly
the kind of cascading failure the rest of this phase's Redis-resilience
work (see app/core/redis.py) is designed to prevent. This is logged at
WARNING, not silently swallowed.
"""

import logging
from typing import Callable, Optional, Tuple, Union

from fastapi import Depends, Request
from fastapi.responses import JSONResponse
from redis.asyncio import Redis
from redis.exceptions import RedisError
from starlette.middleware.base import BaseHTTPMiddleware

from app.core import metrics
from app.core.config import settings
from app.core.errors import AppHTTPException, build_error_body
from app.core.redis import get_redis
from app.dependencies.auth import get_current_user_id

logger = logging.getLogger("rally.rate_limit")

_DEFAULT_WINDOW_SECONDS = 60

# Either a fixed int, or a zero-arg callable resolved fresh on every
# request — every call site below passes a lambda reading straight off
# `settings` (e.g. `lambda: settings.SOS_RATE_LIMIT_PER_MINUTE`) rather
# than a plain int specifically so the limit is never frozen at route-
# registration/import time. That matters both for tests (which routinely
# monkeypatch `settings.X` and expect it to take effect immediately — the
# same "read live settings" rule app/intelligence/thresholds.py follows)
# and, in principle, for any future runtime config reload.
LimitSpec = Union[int, Callable[[], int]]


def _resolve_limit(limit: LimitSpec) -> int:
    return limit() if callable(limit) else limit


def _client_ip(request: Request) -> str:
    """Best-effort caller IP. Trusts X-Forwarded-For's first hop only when
    present (this backend is expected to run behind a single reverse
    proxy/load balancer in any real deployment) — never logged or
    returned to the client verbatim, only ever used as an opaque rate-
    limit bucket key."""
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


async def check_and_consume(redis: Redis, scope: str, identifier: str, limit: int, window_seconds: int) -> Tuple[bool, int]:
    """Returns (allowed, retry_after_seconds). Increments the counter
    regardless of outcome — a caller who's already over the limit and
    keeps hammering the endpoint doesn't get a free pass just because we
    stopped counting; `retry_after_seconds` is the key's remaining TTL,
    i.e. genuinely how long until the window resets."""
    key = f"rate_limit:{scope}:{identifier}"
    try:
        count = await redis.incr(key)
        if count == 1:
            await redis.expire(key, window_seconds)
        if count > limit:
            ttl = await redis.ttl(key)
            return False, max(int(ttl), 1)
        return True, 0
    except RedisError:
        logger.warning("Rate limit check failed (Redis error) for scope=%s — failing open.", scope)
        metrics.increment("redis_errors_total", {"op": "rate_limit"})
        return True, 0


async def _enforce(scope: str, identifier: str, limit_per_minute: int, window_seconds: int) -> None:
    if not settings.RATE_LIMIT_ENABLED:
        return
    try:
        redis = get_redis()
    except RuntimeError:
        return  # Redis not configured at all — fail open, same as a Redis error.

    allowed, retry_after = await check_and_consume(redis, scope, identifier, limit_per_minute, window_seconds)
    if not allowed:
        metrics.increment("rate_limited_total", {"scope": scope})
        raise AppHTTPException(
            status_code=429,
            code="RATE_LIMITED",
            detail="Too many requests",
            extra={"retry_after_seconds": retry_after},
            headers={"Retry-After": str(retry_after)},
        )


def rate_limit_by_user(scope: str, limit_per_minute: LimitSpec, *, window_seconds: int = _DEFAULT_WINDOW_SECONDS) -> Callable:
    """For an endpoint that already requires authentication — the rate
    limit key is the verified user id (never a client-supplied one)."""

    async def _dependency(user_id: str = Depends(get_current_user_id)) -> None:
        await _enforce(scope, f"user:{user_id}", _resolve_limit(limit_per_minute), window_seconds)

    return _dependency


def rate_limit_by_ip(scope: str, limit_per_minute: LimitSpec, *, window_seconds: int = _DEFAULT_WINDOW_SECONDS) -> Callable:
    """For an endpoint reachable without authentication."""

    async def _dependency(request: Request) -> None:
        await _enforce(scope, f"ip:{_client_ip(request)}", _resolve_limit(limit_per_minute), window_seconds)

    return _dependency


class GeneralRateLimitMiddleware(BaseHTTPMiddleware):
    """The catch-all "General API: N requests/minute" limit (Part 3),
    applied to every request regardless of route. Endpoint-specific
    limits (auth, join-group, SOS — see app/api/*.py) are stricter
    overrides layered on top via the dependencies above, not a
    replacement for this one; a request can be rejected by either.

    Decodes the JWT itself, best-effort, purely to key by user id when
    present — never raises on a missing/invalid token (that's every
    route's own auth dependency's job); an unauthenticated or malformed
    request just falls back to IP-based keying."""

    EXEMPT_PATH_PREFIXES = ("/docs", "/redoc", "/openapi.json")

    async def dispatch(self, request: Request, call_next):
        if not settings.RATE_LIMIT_ENABLED or request.url.path in ("/", ) or any(
            request.url.path.startswith(p) for p in self.EXEMPT_PATH_PREFIXES
        ) or request.url.path.endswith("/health"):
            return await call_next(request)

        identifier = self._identify(request)
        try:
            redis = get_redis()
            allowed, retry_after = await check_and_consume(
                redis, "api", identifier, settings.GENERAL_API_RATE_LIMIT_PER_MINUTE, _DEFAULT_WINDOW_SECONDS
            )
        except RuntimeError:
            allowed, retry_after = True, 0  # Redis not configured — fail open.

        if not allowed:
            metrics.increment("rate_limited_total", {"scope": "api"})
            return JSONResponse(
                status_code=429,
                content=build_error_body(
                    code="RATE_LIMITED", message="Too many requests", request=request,
                    extra={"retry_after_seconds": retry_after},
                ),
                headers={"Retry-After": str(retry_after)},
            )

        return await call_next(request)

    @staticmethod
    def _identify(request: Request) -> str:
        auth_header = request.headers.get("authorization", "")
        if auth_header.lower().startswith("bearer "):
            user_id = _best_effort_user_id(auth_header[7:].strip())
            if user_id:
                return f"user:{user_id}"
        return f"ip:{_client_ip(request)}"


def _best_effort_user_id(token: str) -> Optional[str]:
    """Decodes the JWT purely to extract `sub` for rate-limit keying —
    never used for authorization (every route's own dependency chain
    still independently verifies the token before trusting anything about
    the caller). Any failure here just means "key by IP instead," not an
    error response — this middleware must never be where a 401 comes
    from."""
    try:
        from app.core.security import decode_supabase_jwt

        claims = decode_supabase_jwt(token)
        return claims.get("sub")
    except Exception:
        return None
