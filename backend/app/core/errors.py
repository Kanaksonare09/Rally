"""
Consistent error response shape for every failure path. Client-facing
messages never include the raw exception — full details go to the server
log only (see core.logging).

Phase 11 additions: every error response now also carries `request_id`
(so a user-reported failure can be matched to the exact log lines that
handled it — see app/core/middleware.py::RequestIDMiddleware, which sets
`request.state.request_id` before any handler runs) and, where relevant,
extra fields like `retry_after_seconds` for 429s. The envelope itself
(`{"success": false, "error": {...}}`) is unchanged from earlier phases —
deliberately additive, not a breaking redesign, so every existing caller
of `response.json()["error"]["code"]` keeps working.
"""

import logging
from typing import Optional

from fastapi import FastAPI, HTTPException, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

logger = logging.getLogger("rally.errors")


class AppHTTPException(HTTPException):
    """An HTTPException carrying a specific machine-readable error code
    (e.g. "TRIP_NOT_FOUND") instead of the generic per-status-code default.

    `extra` merges additional fields into the response's `error` object
    (e.g. `{"retry_after_seconds": 10}` for a 429 — see
    app/core/rate_limit.py). `headers` passes through to HTTPException
    unchanged, for cases like the `Retry-After` HTTP header that belongs
    on the response itself, not just in the JSON body.
    """

    def __init__(
        self, status_code: int, code: str, detail: str, *, extra: Optional[dict] = None, headers: Optional[dict] = None
    ):
        super().__init__(status_code=status_code, detail=detail, headers=headers)
        self.code = code
        self.extra = extra or {}


def build_error_body(code: str, message: str, request: Request, extra: Optional[dict] = None) -> dict:
    """Public: other modules that hand-build an error response outside the
    normal exception-handler path (e.g. app/core/rate_limit.py's ASGI
    middleware, which runs outside FastAPI's dependency/exception-handling
    machinery entirely) use this directly, so every error response — no
    matter which code path produced it — carries the exact same envelope
    shape."""
    error = {"code": code, "message": message}
    request_id = getattr(request.state, "request_id", None)
    if request_id:
        error["request_id"] = request_id
    if extra:
        error.update(extra)
    return {"success": False, "error": error}


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(HTTPException)
    async def http_exception_handler(request: Request, exc: HTTPException):
        code = getattr(exc, "code", None) or _code_for_status(exc.status_code)
        extra = getattr(exc, "extra", None)
        return JSONResponse(
            status_code=exc.status_code,
            content=build_error_body(code=code, message=str(exc.detail), request=request, extra=extra),
            headers=exc.headers,
        )

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError):
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content=build_error_body(code="VALIDATION_ERROR", message="Request validation failed.", request=request),
        )

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception):
        # Full exception (stack trace, exception type/message) goes to the
        # server log only — the client response below never includes it,
        # in production or otherwise (see the module docstring).
        logger.exception("Unhandled error on %s %s", request.method, request.url.path)
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=build_error_body(code="INTERNAL_ERROR", message="Unable to process request.", request=request),
        )


def _code_for_status(status_code: int) -> str:
    return {
        400: "BAD_REQUEST",
        401: "UNAUTHORIZED",
        403: "FORBIDDEN",
        404: "NOT_FOUND",
        409: "CONFLICT",
        422: "VALIDATION_ERROR",
        429: "RATE_LIMITED",
        500: "INTERNAL_ERROR",
        503: "SERVICE_UNAVAILABLE",
    }.get(status_code, "ERROR")
