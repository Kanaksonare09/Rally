"""
Background scheduler: every INTELLIGENCE_EVALUATION_INTERVAL_SECONDS,
re-evaluates every currently ACTIVE trip. One centralized loop, not one
task per trip or per user — this phase's spec explicitly allows either
"one evaluator per active trip" or "a scalable centralized worker model";
this picks the centralized model for simplicity, since duplicate-
evaluation safety is already guaranteed independently at the Redis-lock
and database-constraint level (see engine.py / events.py), not by this
loop's own structure.

Started once from app.main's lifespan; designed so this loop body (one
tick, over one process) can later be replaced by Celery/RQ/Redis
Streams/Kafka consuming the same evaluate_and_persist_trip() without
touching app/intelligence/engine.py at all.
"""

import asyncio
import logging
import time
from datetime import datetime, timezone
from typing import List, Optional, Tuple
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session
from starlette.concurrency import run_in_threadpool

from app.core import metrics
from app.core.config import settings
from app.core.database import SessionLocal
from app.core.redis import get_redis
from app.intelligence.engine import evaluate_and_persist_trip
from app.models.enums import TripStatus
from app.models.trip import Trip

logger = logging.getLogger("rally.intelligence.worker")

# Updated after every completed tick — read by /health (see
# worker_health_status() below). Process-local, deliberately not in Redis:
# it only needs to answer "is *this instance's* loop alive," which a
# restart trivially resets.
_last_tick_completed_at: Optional[datetime] = None


def _active_trips_sync(db: Session) -> List[Tuple[UUID, UUID]]:
    rows = db.execute(select(Trip.id, Trip.group_id).where(Trip.status == TripStatus.ACTIVE)).all()
    return [(row.id, row.group_id) for row in rows]


async def run_evaluation_tick() -> int:
    """One pass over every active trip. Returns how many trips were
    evaluated (0 if Redis/the database are unavailable — logged, never
    raised, so a transient outage can't crash the whole worker loop)."""
    if SessionLocal is None:
        return 0
    try:
        redis = get_redis()
    except RuntimeError:
        return 0

    db = SessionLocal()
    try:
        try:
            active_trips = await run_in_threadpool(_active_trips_sync, db)
        except Exception:
            logger.exception("Failed to list active trips for intelligence evaluation")
            metrics.increment("intelligence_tick_errors_total", {"stage": "list_active_trips"})
            return 0

        evaluated = 0
        for trip_id, group_id in active_trips:
            start = time.monotonic()
            try:
                await evaluate_and_persist_trip(db, redis, trip_id, group_id)
                evaluated += 1
            except Exception:
                logger.exception("Intelligence evaluation failed for trip_id=%s", trip_id)
                metrics.increment("intelligence_tick_errors_total", {"stage": "evaluate_trip"})
            finally:
                metrics.observe("intelligence_evaluation_duration_ms", (time.monotonic() - start) * 1000)
        return evaluated
    finally:
        db.close()


async def run_intelligence_worker() -> None:
    """Long-lived loop, started as a background task from app.main's
    lifespan and cancelled on shutdown.

    Worker supervision (Part 12): every tick is wrapped in its own
    try/except — a failure logs (never `except: pass`), increments a
    metric, and the loop keeps running on its normal interval, exactly
    like every per-trip evaluation inside run_evaluation_tick() already
    does. Without this, an exception from something run_evaluation_tick()
    itself doesn't already catch internally (e.g. SessionLocal() failing
    to open a new session) would silently kill this entire background
    task — the intelligence engine would stop for the rest of the
    process's life with no log line and no restart."""
    global _last_tick_completed_at
    logger.info(
        "Intelligence worker starting (interval=%.1fs)", settings.INTELLIGENCE_EVALUATION_INTERVAL_SECONDS
    )
    try:
        while True:
            await asyncio.sleep(settings.INTELLIGENCE_EVALUATION_INTERVAL_SECONDS)
            try:
                await run_evaluation_tick()
                _last_tick_completed_at = datetime.now(timezone.utc)
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception("Intelligence worker tick failed unexpectedly — will retry next interval")
                metrics.increment("intelligence_tick_errors_total", {"stage": "tick"})
    except asyncio.CancelledError:
        logger.info("Intelligence worker stopped")
        raise


def worker_health_status() -> str:
    """"ok" once at least one tick has completed recently, "starting" if
    the loop just hasn't ticked yet, "stalled" if it has fallen far behind
    its own interval (e.g. stuck on a slow DB/Redis call) — used by
    GET /health, never exposes internal state beyond this label."""
    if _last_tick_completed_at is None:
        return "starting"
    age = (datetime.now(timezone.utc) - _last_tick_completed_at).total_seconds()
    stalled_after = max(settings.INTELLIGENCE_EVALUATION_INTERVAL_SECONDS * 5, 30)
    return "ok" if age <= stalled_after else "stalled"
