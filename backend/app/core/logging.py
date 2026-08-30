"""
Minimal logging setup. Deliberately never logs request bodies, headers, or
settings values — passwords, JWT secrets, and the Supabase service role
key must never reach a log line. Same rule extends to precise GPS
coordinates and full SOS messages — see app/core/middleware.py's
RequestIDMiddleware and the backend README's Logging section for exactly
what does and doesn't get logged.
"""

import logging

_VALID_LEVELS = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}


def configure_logging(environment: str, log_level: str = "INFO") -> None:
    """`log_level` (settings.LOG_LEVEL) is the explicit override and wins
    whenever it's a recognized level name; otherwise falls back to the
    same environment-based default this always had (DEBUG in development,
    INFO everywhere else) — production should not run at DEBUG by
    default, and this function's own fallback enforces that even if
    LOG_LEVEL is left unset or misspelled."""
    normalized = (log_level or "").upper()
    if normalized in _VALID_LEVELS:
        level = getattr(logging, normalized)
    else:
        level = logging.DEBUG if environment == "development" else logging.INFO

    logging.basicConfig(
        level=level,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    # Quiet the noisiest third-party loggers unless something actually breaks.
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
