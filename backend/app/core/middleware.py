"""
HTTP-only ASGI middleware (BaseHTTPMiddleware only ever wraps `http`-scope
requests — a WebSocket `upgrade` request passes through untouched, so
nothing here can break WS tracking, per this phase's explicit "do not add
headers that break WebSockets" instruction).

RequestIDMiddleware: generates or reuses X-Request-ID, exposes it as
`request.state.request_id` (read by app/core/errors.py so every error body
includes it), and logs one structured line per request. Deliberately logs
only method/path/status_code/duration_ms/request_id — never headers, query
strings, or bodies, so a JWT/Authorization header, join code, or GPS
coordinate can never end up in a log line via this path.

SecurityHeadersMiddleware: a small set of standard, low-risk response
headers. Nothing here is CSP/HSTS-strength hardening (out of scope for a
demo-grade backend with no server-rendered HTML to protect) — just the
handful of headers that cost nothing and catch the obvious cases (MIME
sniffing, clickjacking).
"""

import logging
import time
import uuid
from typing import Callable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from app.core import metrics
from app.core.config import settings
from app.core.errors import build_error_body

logger = logging.getLogger("rally.requests")

REQUEST_ID_HEADER = "X-Request-ID"
_MAX_REQUEST_ID_LENGTH = 128


def _is_safe_request_id(value: str) -> bool:
    """A conservative accept-list for a client-supplied X-Request-ID:
    reasonable length, safe characters only. A request id that fails this
    is replaced with a freshly generated one rather than echoed back —
    never trust/relay arbitrary client-controlled header content into logs
    or other clients' responses unvalidated."""
    return 1 <= len(value) <= _MAX_REQUEST_ID_LENGTH and all(c.isalnum() or c in "-_." for c in value)


def _route_template(request: Request) -> str:
    """The path *template* ("/trips/{trip_id}/analytics"), not the
    resolved path with real UUIDs in it — keeps metric label cardinality
    bounded regardless of how many distinct trips/users hit the API.
    Falls back to the raw path if routing didn't resolve (e.g. a 404 for
    a path matching no route at all)."""
    route = request.scope.get("route")
    path = getattr(route, "path", None)
    return path or request.url.path


class RequestIDMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        incoming = request.headers.get(REQUEST_ID_HEADER)
        request_id = incoming if incoming and _is_safe_request_id(incoming) else str(uuid.uuid4())
        request.state.request_id = request_id

        start = time.monotonic()
        try:
            response = await call_next(request)
        except Exception:
            duration_ms = (time.monotonic() - start) * 1000
            metrics.increment("http_requests_total", {"method": request.method, "status": "500"})
            metrics.increment("http_errors_total")
            metrics.observe("http_request_duration_ms", duration_ms, {"method": request.method})
            logger.error(
                "request_id=%s method=%s path=%s status_code=500 duration_ms=%.1f",
                request_id, request.method, request.url.path, duration_ms,
            )
            raise

        duration_ms = (time.monotonic() - start) * 1000
        response.headers[REQUEST_ID_HEADER] = request_id

        route_label = _route_template(request)
        metrics.increment("http_requests_total", {"method": request.method, "status": str(response.status_code)})
        metrics.observe("http_request_duration_ms", duration_ms, {"method": request.method, "route": route_label})
        if response.status_code == 429:
            metrics.increment("http_rate_limited_total", {"route": route_label})
        if response.status_code >= 500:
            metrics.increment("http_errors_total")

        log_level = logging.WARNING if response.status_code >= 400 else logging.INFO
        logger.log(
            log_level,
            "request_id=%s method=%s path=%s status_code=%s duration_ms=%.1f",
            request_id, request.method, request.url.path, response.status_code, duration_ms,
        )
        return response


class MaxBodySizeMiddleware(BaseHTTPMiddleware):
    """Rejects a request outright (413) when its declared Content-Length
    exceeds MAX_REQUEST_BODY_BYTES — checked from the header alone, before
    Starlette/Pydantic ever reads or buffers the body, so an oversized
    payload costs this server nothing beyond parsing one header. A
    request with no Content-Length (chunked transfer encoding — not used
    by any client this API expects) passes through unchecked; that's a
    known, accepted gap, not a silent bypass anyone would hit in normal
    use of this API."""

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        content_length = request.headers.get("content-length")
        if content_length is not None:
            try:
                declared_size = int(content_length)
            except ValueError:
                declared_size = None
            if declared_size is not None and declared_size > settings.MAX_REQUEST_BODY_BYTES:
                metrics.increment("http_requests_rejected_total", {"reason": "body_too_large"})
                return JSONResponse(
                    status_code=413,
                    content=build_error_body(
                        code="PAYLOAD_TOO_LARGE",
                        message=f"Request body exceeds the {settings.MAX_REQUEST_BODY_BYTES} byte limit.",
                        request=request,
                    ),
                )
        return await call_next(request)


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        response = await call_next(request)
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        return response
