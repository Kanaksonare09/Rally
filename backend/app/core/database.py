"""
SQLAlchemy engine/session setup, targeting Supabase Postgres directly via
DATABASE_URL. Synchronous engine on purpose: this phase has no concurrent
WebSocket load yet (that's deferred), and a sync engine keeps Alembic and the
rest of the stack simpler for now — it can move to asyncpg later without
touching the schema.
"""

import logging
from contextlib import contextmanager
from typing import Generator

from sqlalchemy import create_engine, text
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.core.config import settings

logger = logging.getLogger("rally.database")


class Base(DeclarativeBase):
    pass


def _normalize_driver(database_url: str) -> str:
    """requirements.txt installs psycopg (v3), not psycopg2. Supabase (and
    most docs) hand out connection strings as a bare `postgresql://`, which
    SQLAlchemy resolves to the legacy psycopg2 dialect by default — that
    import fails since psycopg2 was never installed. Rewrite to the
    dialect that's actually present instead of requiring every DATABASE_URL
    to be hand-edited with `+psycopg`."""
    if database_url.startswith("postgresql://"):
        return "postgresql+psycopg://" + database_url[len("postgresql://") :]
    return database_url


def _build_engine():
    if not settings.DATABASE_URL:
        # Defer the failure until something actually tries to use the DB —
        # this lets `import app.main` / model imports succeed even before
        # a .env is configured, which the test suite relies on.
        logger.warning("DATABASE_URL is not set - database calls will fail until it is configured.")
        return None
    return create_engine(
        _normalize_driver(settings.DATABASE_URL),
        # Part 6 — Database resilience: a bounded, reused connection pool
        # instead of one connection per request. pool_pre_ping issues a
        # cheap liveness check before handing out a pooled connection, so
        # a connection Supabase silently dropped server-side is replaced
        # rather than surfacing as a confusing mid-query failure;
        # pool_recycle backs that up by proactively retiring connections
        # older than DATABASE_POOL_RECYCLE_SECONDS regardless.
        pool_pre_ping=True,
        pool_size=settings.DATABASE_POOL_SIZE,
        max_overflow=settings.DATABASE_MAX_OVERFLOW,
        pool_timeout=settings.DATABASE_POOL_TIMEOUT_SECONDS,
        pool_recycle=settings.DATABASE_POOL_RECYCLE_SECONDS,
        future=True,
    )


engine = _build_engine()

SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True) if engine else None


def get_db() -> Generator[Session, None, None]:
    if SessionLocal is None:
        raise RuntimeError("Database is not configured. Set DATABASE_URL in your environment.")
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


@contextmanager
def session_scope() -> Generator[Session, None, None]:
    """Context-manager variant of get_db, for use outside FastAPI's Depends()."""
    if SessionLocal is None:
        raise RuntimeError("Database is not configured. Set DATABASE_URL in your environment.")
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def close_database() -> None:
    """Call once during app shutdown (Part 12 — graceful shutdown): disposes
    the connection pool so every pooled connection is closed cleanly
    rather than left for the OS to clean up when the process exits."""
    if engine is not None:
        engine.dispose()


def check_database_connection() -> bool:
    """Used by /health — never raises, just reports reachability."""
    if engine is None:
        return False
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception as exc:
        logger.error("Database health check failed: %s", exc)
        return False
