"""
SOS: an explicitly user-triggered emergency, entirely separate from the
Alert Engine (app/alerts/) — an SOS is never generated from an
intelligence event in this phase, and an alert is never auto-escalated
into an SOS.

SOS SAFETY RULE: a WebSocket disconnect, stale GPS, a user going offline,
or a Redis TTL expiring must NEVER cancel or resolve an SOS. Its lifecycle
is governed exclusively by explicit acknowledge/resolve/cancel calls —
which is also exactly why nothing here puts a TTL on the Redis active-SOS
mirror; TTLs are for live-location/presence state
(app/services/{live_state_service,presence_service}.py), which has no
bearing on SOS at all.

PostgreSQL is written first and is the permanent record; Redis is a
disposable fast-path mirror of "this SOS is currently active" — a Redis
failure here never means the SOS itself was lost.
"""

import json
import logging
import uuid
from datetime import datetime, timezone
from typing import List, Optional

from redis.asyncio import Redis
from sqlalchemy import select
from sqlalchemy.orm import Session
from starlette.concurrency import run_in_threadpool

from app.core import metrics
from app.core.errors import AppHTTPException
from app.core.redis_keys import sos_active_key, trip_active_sos_key
from app.models.enums import SOSStatus
from app.models.sos_event import SOSEvent
from app.notifications import service as notification_service
from app.schemas.sos import SOSCreate
from app.websocket.manager import publish_event
from app.websocket.schemas import build_sos, build_sos_updated

logger = logging.getLogger("rally.sos")


def _point_wkt(latitude: float, longitude: float) -> str:
    return f"POINT({longitude} {latitude})"


def _get_active_sos_for_user_sync(db: Session, trip_id: uuid.UUID, user_id: uuid.UUID) -> Optional[SOSEvent]:
    """Idempotency check (Part 7): a retried/duplicate SOS trigger for the
    same user on the same trip must never create a second row while one
    is already ACTIVE or ACKNOWLEDGED — a flaky connection retrying the
    request, or a panicked user tapping the button twice, must not spawn
    two emergencies. RESOLVED/CANCELLED SOS events don't block a new
    trigger; a past emergency being over is exactly when a new one is
    legitimate."""
    stmt = select(SOSEvent).where(
        SOSEvent.trip_id == trip_id,
        SOSEvent.user_id == user_id,
        SOSEvent.status.in_((SOSStatus.ACTIVE, SOSStatus.ACKNOWLEDGED)),
    )
    return db.scalars(stmt).first()


def _create_sos_sync(
    db: Session, trip_id: uuid.UUID, group_id: uuid.UUID, user_id: uuid.UUID, data: SOSCreate
) -> SOSEvent:
    sos = SOSEvent(
        trip_id=trip_id,
        group_id=group_id,
        user_id=user_id,
        latitude=data.latitude,
        longitude=data.longitude,
        accuracy=data.accuracy,
        location=_point_wkt(data.latitude, data.longitude),
        message=data.message,
        status=SOSStatus.ACTIVE,
    )
    db.add(sos)
    db.commit()
    db.refresh(sos)
    return sos


async def _publish(redis: Optional[Redis], trip_id: uuid.UUID, message: dict) -> None:
    if redis is None:
        logger.warning("Redis not configured; skipping SOS broadcast for trip %s.", trip_id)
        return
    try:
        await publish_event(redis, str(trip_id), message)
    except Exception:
        logger.exception("Failed to publish SOS event for trip %s", trip_id)


async def trigger_sos(
    db: Session,
    redis: Optional[Redis],
    trip_id: uuid.UUID,
    group_id: uuid.UUID,
    user_id: uuid.UUID,
    data: SOSCreate,
) -> SOSEvent:
    existing = await run_in_threadpool(_get_active_sos_for_user_sync, db, trip_id, user_id)
    if existing is not None:
        # Idempotent, not an error: the caller gets the SAME emergency
        # back (already broadcast when it was first created), rather than
        # a rejection or a second, duplicate one — see
        # _get_active_sos_for_user_sync's docstring.
        logger.info("Duplicate SOS trigger for trip_id=%s user_id=%s — returning existing sos_id=%s", trip_id, user_id, existing.id)
        return existing

    sos = await run_in_threadpool(_create_sos_sync, db, trip_id, group_id, user_id, data)
    metrics.increment("sos_triggered_total")

    # Every active group member is notified, including the trigger user
    # themselves (a confirmation that their SOS was recorded) — unlike
    # alerts, there's no "not worth telling the person it's about"
    # distinction for an emergency. dedup_key ties to this exact SOS row
    # per recipient, so it's a no-op on the (already-deduplicated-above)
    # retry path.
    await run_in_threadpool(
        notification_service.notify_group_safely,
        db, group_id=group_id, type="SOS", title="SOS emergency",
        message="A group member has triggered an SOS emergency.", severity="CRITICAL", trip_id=trip_id,
        dedup_key_fn=lambda uid: f"sos:{sos.id}:{uid}", metadata={"sos_id": str(sos.id)},
    )

    if redis is not None:
        try:
            payload = json.dumps(
                {
                    "id": str(sos.id),
                    "trip_id": str(trip_id),
                    "user_id": str(user_id),
                    "latitude": sos.latitude,
                    "longitude": sos.longitude,
                    "status": sos.status.value,
                    "triggered_at": sos.triggered_at.isoformat(),
                }
            )
            # No TTL — see the module docstring's SOS SAFETY RULE.
            async with redis.pipeline(transaction=True) as pipe:
                pipe.set(sos_active_key(trip_id, sos.id), payload)
                pipe.sadd(trip_active_sos_key(trip_id), str(sos.id))
                await pipe.execute()
        except Exception:
            logger.exception("Failed to register active SOS state in Redis for sos_id=%s", sos.id)

    await _publish(
        redis,
        trip_id,
        build_sos(
            sos_id=sos.id, trip_id=trip_id, user_id=user_id, latitude=sos.latitude, longitude=sos.longitude,
            accuracy=sos.accuracy, message=sos.message, status=sos.status.value,
            triggered_at=sos.triggered_at.isoformat(),
        ),
    )
    return sos


def get_sos_by_id(db: Session, sos_id: uuid.UUID) -> Optional[SOSEvent]:
    return db.get(SOSEvent, sos_id)


def _acknowledge_sync(db: Session, sos: SOSEvent) -> SOSEvent:
    if sos.status != SOSStatus.ACTIVE:
        raise AppHTTPException(
            status_code=409, code="INVALID_SOS_STATE", detail="Only an ACTIVE SOS can be acknowledged."
        )
    sos.status = SOSStatus.ACKNOWLEDGED
    sos.acknowledged_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(sos)
    return sos


def _resolve_sync(db: Session, sos: SOSEvent) -> SOSEvent:
    if sos.status not in (SOSStatus.ACTIVE, SOSStatus.ACKNOWLEDGED):
        raise AppHTTPException(
            status_code=409, code="INVALID_SOS_STATE", detail="Only an ACTIVE or ACKNOWLEDGED SOS can be resolved."
        )
    sos.status = SOSStatus.RESOLVED
    sos.resolved_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(sos)
    metrics.increment("sos_resolved_total")
    return sos


def _cancel_sync(db: Session, sos: SOSEvent, requesting_user_id: uuid.UUID) -> SOSEvent:
    if sos.user_id != requesting_user_id:
        raise AppHTTPException(
            status_code=403, code="FORBIDDEN", detail="Only the person who triggered this SOS can cancel it."
        )
    if sos.status not in (SOSStatus.ACTIVE, SOSStatus.ACKNOWLEDGED):
        raise AppHTTPException(
            status_code=409, code="INVALID_SOS_STATE", detail="This SOS can no longer be cancelled."
        )
    sos.status = SOSStatus.CANCELLED
    sos.resolved_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(sos)
    return sos


async def _clear_active_state(redis: Optional[Redis], trip_id: uuid.UUID, sos_id: uuid.UUID) -> None:
    """Removes the disposable Redis mirror after resolve/cancel.
    PostgreSQL's record is untouched and remains the permanent history."""
    if redis is None:
        return
    try:
        await redis.delete(sos_active_key(trip_id, sos_id))
        await redis.srem(trip_active_sos_key(trip_id), str(sos_id))
    except Exception:
        logger.exception("Failed to clear active SOS Redis state for sos_id=%s", sos_id)


async def acknowledge_sos(db: Session, redis: Optional[Redis], sos: SOSEvent) -> SOSEvent:
    updated = await run_in_threadpool(_acknowledge_sync, db, sos)
    await _publish(redis, updated.trip_id, build_sos_updated(updated.id, updated.status.value))
    return updated


async def resolve_sos(db: Session, redis: Optional[Redis], sos: SOSEvent) -> SOSEvent:
    updated = await run_in_threadpool(_resolve_sync, db, sos)
    await _clear_active_state(redis, updated.trip_id, updated.id)
    await _publish(redis, updated.trip_id, build_sos_updated(updated.id, updated.status.value))
    return updated


async def cancel_sos(db: Session, redis: Optional[Redis], sos: SOSEvent, requesting_user_id: uuid.UUID) -> SOSEvent:
    updated = await run_in_threadpool(_cancel_sync, db, sos, requesting_user_id)
    await _clear_active_state(redis, updated.trip_id, updated.id)
    await _publish(redis, updated.trip_id, build_sos_updated(updated.id, updated.status.value))
    return updated


def list_sos(db: Session, trip_id: uuid.UUID, *, status: Optional[SOSStatus] = None, limit: int = 100) -> List[SOSEvent]:
    stmt = select(SOSEvent).where(SOSEvent.trip_id == trip_id)
    if status is not None:
        stmt = stmt.where(SOSEvent.status == status)
    stmt = stmt.order_by(SOSEvent.triggered_at.desc()).limit(limit)
    return list(db.scalars(stmt).all())


def list_active_sos(db: Session, trip_id: uuid.UUID) -> List[SOSEvent]:
    stmt = (
        select(SOSEvent)
        .where(SOSEvent.trip_id == trip_id, SOSEvent.status.in_([SOSStatus.ACTIVE, SOSStatus.ACKNOWLEDGED]))
        .order_by(SOSEvent.triggered_at.desc())
    )
    return list(db.scalars(stmt).all())
