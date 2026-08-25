"""
Minimal logging setup. Deliberately never logs request bodies, headers, or
settings values — passwords, JWT secrets, and the Supabase service role key
must never reach a log line.
"""

import logging


def configure_logging(environment: str) -> None:
    level = logging.DEBUG if environment == "development" else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    # Quiet the noisiest third-party loggers unless something actually breaks.
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
