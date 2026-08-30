"""
The Alert Engine: decides whether a Phase 7 intelligence_event becomes a
user-facing alert (app/alerts/policies.py), persists/acknowledges/resolves
that alert, and publishes it over the trip's WebSocket channel — reusing
the exact same Redis Pub/Sub mechanism location/intelligence events use
(app.websocket.manager.publish_event), never a parallel one.

Kept entirely separate from app/intelligence/: detectors never know
alerts exist; this module is the only consumer of IntelligenceEvent rows
for the purpose of deciding whether to notify anyone. Recipients aren't
computed/stored here — "all active members of the trip's group" is
already exactly who's authorized on the trip's WebSocket channel, so the
broadcast scope IS the recipient list.
"""

import uuid
from datetime import datetime, timezone
from typing import List, Optional

from redis.asyncio import Redis
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from starlette.concurrency import run_in_threadpool

from app.alerts.policies import get_policy
from app.core import metrics
from app.core.errors import AppHTTPException
from app.core.redis_keys import alert_dedup_lock_key
from app.models.alert import Alert
from app.models.enums import AlertSeverity, AlertStatus, AlertType
from app.models.intelligence_event import IntelligenceEvent
from app.notifications import service as notification_service
from app.websocket.manager import publish_event
from app.websocket.schemas import build_alert, build_alert_updated


def _point_wkt(latitude: Optional[float], longitude: Optional[float]) -> Optional[str]:
    if latitude is None or longitude is None:
        return None
    return f"POINT({longitude} {latitude})"


def _get_unresolved_alert_for_event_sync(db: Session, event_id: uuid.UUID) -> Optional[Alert]:
    stmt = select(Alert).where(Alert.event_id == event_id, Alert.resolved_at.is_(None))
    return db.scalars(stmt).first()


def _create_alert_sync(db: Session, event: IntelligenceEvent, policy) -> Optional[Alert]:
    alert = Alert(
        group_id=event.group_id,
        trip_id=event.trip_id,
        event_id=event.id,
        alert_type=policy.alert_type,
        severity=policy.severity,
        status=AlertStatus.ACTIVE,
        user_id=event.user_id,
        related_user_id=event.related_user_id,
        title=policy.title,
        message=policy.message_fn(event.event_metadata or {}),
        location=_point_wkt(event.latitude, event.longitude),
        alert_metadata=event.event_metadata or {},
    )
    db.add(alert)
    try:
        db.commit()
    except IntegrityError:
        # Another evaluator's alert for this same event won the race — the
        # database's partial unique index on (event_id) WHERE resolved_at
        # IS NULL is what actually guarantees no duplicate, not this check.
        db.rollback()
        return None
    db.refresh(alert)
    metrics.increment("alerts_generated_total", {"alert_type": alert.alert_type.value})
    return alert


def _notify_for_alert_sync(db: Session, alert: Alert) -> None:
    """A per-user alert notifies just that member; a group-level alert
    (user_id is None — e.g. GROUP_SEPARATION) notifies every active group
    member (app/notifications/service.py::notify_group_safely). dedup_key
    ties to this exact alert row, so a later metadata refresh on the SAME
    ongoing alert (an "updated" action, which never reaches this function
    at all — see apply_intelligence_event) can never double-notify; only
    a genuinely new alert (a new row) does."""
    if alert.user_id is not None:
        notification_service.notify_safely(
            db, user_id=alert.user_id, type=alert.alert_type.value, title=alert.title, message=alert.message,
            severity=alert.severity.value, trip_id=alert.trip_id, dedup_key=f"alert:{alert.id}",
            metadata={"alert_id": str(alert.id)},
        )
        return

    notification_service.notify_group_safely(
        db, group_id=alert.group_id, type=alert.alert_type.value, title=alert.title, message=alert.message,
        severity=alert.severity.value, trip_id=alert.trip_id,
        dedup_key_fn=lambda uid: f"alert:{alert.id}:{uid}", metadata={"alert_id": str(alert.id)},
    )


def _resolve_alert_sync(db: Session, alert: Alert) -> None:
    alert.status = AlertStatus.RESOLVED
    alert.resolved_at = datetime.now(timezone.utc)
    db.commit()
    metrics.increment("alerts_resolved_total", {"alert_type": alert.alert_type.value})


async def apply_intelligence_event(
    db: Session, redis: Redis, event: Optional[IntelligenceEvent], action: str
) -> None:
    """Called by app/intelligence/engine.py right after it persists a
    detection transition. `action` mirrors events.apply_detection()'s own
    vocabulary ("created"/"updated"/"resolved"/"noop"). Only "created" and
    "resolved" ever change anything here — an "updated" (still-active,
    metadata refreshed) intelligence event doesn't need a fresh alert,
    it's the same ongoing one."""
    if event is None or action not in ("created", "resolved"):
        return

    policy = get_policy(event.event_type)
    if policy is None:
        return  # no alert policy for this event type (e.g. INFO-level states)

    if action == "created":
        # Dedup lock closes the common-case race window fast; the
        # database's partial unique index is the actual guarantee if two
        # evaluations still land here at the same instant.
        lock_key = alert_dedup_lock_key(event.id)
        acquired = await redis.set(lock_key, "1", nx=True, px=10_000)
        if not acquired:
            return

        existing = await run_in_threadpool(_get_unresolved_alert_for_event_sync, db, event.id)
        if existing is not None:
            return

        alert = await run_in_threadpool(_create_alert_sync, db, event, policy)
        if alert is None:
            return

        message = build_alert(
            alert_id=alert.id,
            alert_type=alert.alert_type.value,
            severity=alert.severity.value,
            title=alert.title,
            message=alert.message,
            user_id=alert.user_id,
            created_at=alert.created_at.isoformat(),
        )
        await publish_event(redis, str(alert.trip_id), message)
        await run_in_threadpool(_notify_for_alert_sync, db, alert)

    elif action == "resolved":
        existing = await run_in_threadpool(_get_unresolved_alert_for_event_sync, db, event.id)
        if existing is None:
            return  # never became an alert, or already resolved

        await run_in_threadpool(_resolve_alert_sync, db, existing)
        message = build_alert_updated(existing.id, AlertStatus.RESOLVED.value)
        await publish_event(redis, str(existing.trip_id), message)


# ---- REST-facing operations -------------------------------------------


def get_alert_by_id(db: Session, alert_id: uuid.UUID) -> Optional[Alert]:
    return db.get(Alert, alert_id)


def acknowledge_alert(db: Session, alert: Alert) -> Alert:
    if alert.status != AlertStatus.ACTIVE:
        raise AppHTTPException(
            status_code=409, code="INVALID_ALERT_STATE", detail="Only an ACTIVE alert can be acknowledged."
        )
    alert.status = AlertStatus.ACKNOWLEDGED
    alert.acknowledged_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(alert)
    return alert


def resolve_alert(db: Session, alert: Alert) -> Alert:
    if alert.resolved_at is not None:
        raise AppHTTPException(
            status_code=409, code="INVALID_ALERT_STATE", detail="This alert is already resolved."
        )
    alert.status = AlertStatus.RESOLVED
    alert.resolved_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(alert)
    return alert


def list_alerts(
    db: Session,
    trip_id: uuid.UUID,
    *,
    status: Optional[AlertStatus] = None,
    severity: Optional[AlertSeverity] = None,
    alert_type: Optional[AlertType] = None,
    user_id: Optional[uuid.UUID] = None,
    from_time: Optional[datetime] = None,
    to_time: Optional[datetime] = None,
    limit: int = 100,
) -> List[Alert]:
    stmt = select(Alert).where(Alert.trip_id == trip_id)

    if status is not None:
        stmt = stmt.where(Alert.status == status)
    if severity is not None:
        stmt = stmt.where(Alert.severity == severity)
    if alert_type is not None:
        stmt = stmt.where(Alert.alert_type == alert_type)
    if user_id is not None:
        stmt = stmt.where(Alert.user_id == user_id)
    if from_time is not None:
        stmt = stmt.where(Alert.created_at >= from_time)
    if to_time is not None:
        stmt = stmt.where(Alert.created_at <= to_time)

    stmt = stmt.order_by(Alert.created_at.desc()).limit(limit)
    return list(db.scalars(stmt).all())


def list_active_alerts(db: Session, trip_id: uuid.UUID) -> List[Alert]:
    """ACTIVE or ACKNOWLEDGED — anything not yet RESOLVED."""
    stmt = (
        select(Alert)
        .where(Alert.trip_id == trip_id, Alert.resolved_at.is_(None))
        .order_by(Alert.created_at.desc())
    )
    return list(db.scalars(stmt).all())
