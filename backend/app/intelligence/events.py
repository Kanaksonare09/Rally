"""
Turning a DetectionResult into (at most) one durable row in
intelligence_events — created once, updated in place while it stays
active, resolved when the condition clears. Never a new row per
evaluation tick for the same ongoing condition (the "no duplicate events"
section of this phase's spec).

The partial unique index on (trip_id, event_type, user_id) WHERE
resolved_at IS NULL (see app/models/intelligence_event.py) is the actual
guarantee against two concurrent evaluators both inserting an active
event for the same subject — this module's own "check, then create"
sequence closes the common-case window, but only that index is safe
against two evaluations racing past the check at the same instant (same
pattern as trip_service.start_trip's one-active-trip-per-group guarantee).

The Redis `intel_active_event_key` is a secondary, disposable mirror of
"which event id is currently active for this subject" — convenient for
other code that wants to know without a query, never the source of truth.
"""

import uuid
from datetime import datetime, timezone
from typing import List, Optional, Tuple

from redis.asyncio import Redis
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from starlette.concurrency import run_in_threadpool

from app.core import metrics
from app.core.redis_keys import intel_active_event_key
from app.intelligence.detectors import GROUP_SUBJECT, DetectionResult
from app.models.intelligence_event import IntelligenceEvent

_ACTIVE_EVENT_MIRROR_TTL_SECONDS = 3600


def _point_wkt(latitude: Optional[float], longitude: Optional[float]) -> Optional[str]:
    if latitude is None or longitude is None:
        return None
    return f"POINT({longitude} {latitude})"


def _get_active_event_sync(
    db: Session, trip_id: uuid.UUID, event_type, user_id: Optional[uuid.UUID]
) -> Optional[IntelligenceEvent]:
    stmt = select(IntelligenceEvent).where(
        IntelligenceEvent.trip_id == trip_id,
        IntelligenceEvent.event_type == event_type,
        IntelligenceEvent.resolved_at.is_(None),
    )
    stmt = (
        stmt.where(IntelligenceEvent.user_id == user_id)
        if user_id is not None
        else stmt.where(IntelligenceEvent.user_id.is_(None))
    )
    return db.scalars(stmt).first()


def _create_event_sync(
    db: Session,
    trip_id: uuid.UUID,
    group_id: uuid.UUID,
    result: DetectionResult,
    user_id: Optional[uuid.UUID],
    related_user_id: Optional[uuid.UUID],
    latitude: Optional[float],
    longitude: Optional[float],
) -> Optional[IntelligenceEvent]:
    event = IntelligenceEvent(
        trip_id=trip_id,
        group_id=group_id,
        event_type=result.event_type,
        severity=result.severity,
        user_id=user_id,
        related_user_id=related_user_id,
        latitude=latitude,
        longitude=longitude,
        location=_point_wkt(latitude, longitude),
        event_metadata=result.metadata,
    )
    db.add(event)
    try:
        db.commit()
    except IntegrityError:
        # A concurrent evaluator won the race for this exact subject —
        # they own the active event now, which is exactly the outcome the
        # partial unique index exists to guarantee.
        db.rollback()
        return None
    db.refresh(event)
    metrics.increment("intelligence_events_generated_total", {"event_type": event.event_type.value})
    return event


def _touch_event_sync(
    db: Session, event: IntelligenceEvent, metadata: dict, latitude: Optional[float], longitude: Optional[float]
) -> None:
    event.event_metadata = metadata
    if latitude is not None and longitude is not None:
        event.latitude = latitude
        event.longitude = longitude
        event.location = _point_wkt(latitude, longitude)
    db.commit()


def _resolve_event_sync(db: Session, event: IntelligenceEvent) -> None:
    event.resolved_at = datetime.now(timezone.utc)
    db.commit()


async def apply_detection(
    db: Session,
    redis: Redis,
    trip_id: uuid.UUID,
    group_id: uuid.UUID,
    result: DetectionResult,
    latitude: Optional[float] = None,
    longitude: Optional[float] = None,
) -> Tuple[Optional[IntelligenceEvent], str]:
    """Applies one DetectionResult against current DB state. Returns
    (event, action) where action is "created" / "updated" / "resolved" /
    "noop" — app/intelligence/engine.py uses that to decide whether to
    publish a WebSocket frame (only on created/resolved, never on a
    same-condition "updated" tick — see the dedup section of the spec)."""
    user_id = uuid.UUID(result.user_id) if result.user_id else None
    related_user_id = uuid.UUID(result.related_user_id) if result.related_user_id else None
    subject = result.user_id or GROUP_SUBJECT
    active_key = intel_active_event_key(trip_id, result.event_type.value, subject)

    existing = await run_in_threadpool(_get_active_event_sync, db, trip_id, result.event_type, user_id)

    if result.detected:
        if existing is not None:
            await run_in_threadpool(_touch_event_sync, db, existing, result.metadata, latitude, longitude)
            return existing, "updated"

        created = await run_in_threadpool(
            _create_event_sync, db, trip_id, group_id, result, user_id, related_user_id, latitude, longitude
        )
        if created is None:
            return None, "noop"

        await redis.set(active_key, str(created.id), ex=_ACTIVE_EVENT_MIRROR_TTL_SECONDS)
        return created, "created"

    if existing is not None:
        await run_in_threadpool(_resolve_event_sync, db, existing)
        await redis.delete(active_key)
        return existing, "resolved"

    return None, "noop"


def list_events(
    db: Session,
    trip_id: uuid.UUID,
    *,
    event_type=None,
    severity=None,
    user_id: Optional[uuid.UUID] = None,
    active_only: bool = False,
    from_time: Optional[datetime] = None,
    to_time: Optional[datetime] = None,
    limit: int = 100,
) -> List[IntelligenceEvent]:
    """GET /trips/{trip_id}/intelligence-events — always scoped to the one
    trip in the URL (never cross-trip), newest first."""
    stmt = select(IntelligenceEvent).where(IntelligenceEvent.trip_id == trip_id)

    if event_type is not None:
        stmt = stmt.where(IntelligenceEvent.event_type == event_type)
    if severity is not None:
        stmt = stmt.where(IntelligenceEvent.severity == severity)
    if user_id is not None:
        stmt = stmt.where(IntelligenceEvent.user_id == user_id)
    if active_only:
        stmt = stmt.where(IntelligenceEvent.resolved_at.is_(None))
    if from_time is not None:
        stmt = stmt.where(IntelligenceEvent.detected_at >= from_time)
    if to_time is not None:
        stmt = stmt.where(IntelligenceEvent.detected_at <= to_time)

    stmt = stmt.order_by(IntelligenceEvent.detected_at.desc()).limit(limit)
    return list(db.scalars(stmt).all())


def list_active_events(db: Session, trip_id: uuid.UUID) -> List[IntelligenceEvent]:
    """Used by GET /trips/{trip_id}/intelligence's `active_events` field."""
    return list_events(db, trip_id, active_only=True, limit=1000)
