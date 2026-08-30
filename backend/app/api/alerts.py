import logging
import uuid
from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from starlette.concurrency import run_in_threadpool

from app.alerts import service as alerts_service
from app.core.database import get_db
from app.core.redis import get_redis
from app.dependencies.alert import require_alert_member
from app.dependencies.trip import require_trip_member
from app.models.alert import Alert
from app.models.enums import AlertSeverity, AlertStatus, AlertType
from app.models.trip import Trip
from app.schemas.alert import DEFAULT_ALERTS_LIMIT, MAX_ALERTS_LIMIT, AlertResponse
from app.websocket.manager import publish_event
from app.websocket.schemas import build_alert_updated

logger = logging.getLogger("rally.alerts")

router = APIRouter(tags=["Alerts"])


def _serialize(alert: Alert) -> AlertResponse:
    return AlertResponse(
        id=alert.id,
        trip_id=alert.trip_id,
        event_id=alert.event_id,
        alert_type=alert.alert_type,
        severity=alert.severity,
        status=alert.status,
        title=alert.title,
        message=alert.message,
        user_id=alert.user_id,
        related_user_id=alert.related_user_id,
        metadata=alert.alert_metadata,
        created_at=alert.created_at,
        acknowledged_at=alert.acknowledged_at,
        resolved_at=alert.resolved_at,
    )


async def _publish_alert_updated(alert: Alert) -> None:
    try:
        redis = get_redis()
    except RuntimeError:
        logger.warning("Redis not configured; skipping alert_updated broadcast for alert %s.", alert.id)
        return
    try:
        await publish_event(redis, str(alert.trip_id), build_alert_updated(alert.id, alert.status.value))
    except Exception:
        logger.exception("Failed to publish alert_updated for alert %s", alert.id)


@router.get("/trips/{trip_id}/alerts", response_model=List[AlertResponse])
def list_trip_alerts_endpoint(
    trip: Trip = Depends(require_trip_member),
    db: Session = Depends(get_db),
    status: Optional[AlertStatus] = Query(None),
    severity: Optional[AlertSeverity] = Query(None),
    alert_type: Optional[AlertType] = Query(None),
    user_id: Optional[uuid.UUID] = Query(None),
    from_: Optional[datetime] = Query(None, alias="from"),
    to: Optional[datetime] = Query(None),
    limit: int = Query(DEFAULT_ALERTS_LIMIT, ge=1, le=MAX_ALERTS_LIMIT),
):
    """All alerts for the trip, newest first. Always scoped to the one
    trip in the URL — never cross-trip, regardless of filters."""
    rows = alerts_service.list_alerts(
        db,
        trip.id,
        status=status,
        severity=severity,
        alert_type=alert_type,
        user_id=user_id,
        from_time=from_,
        to_time=to,
        limit=limit,
    )
    return [_serialize(a) for a in rows]


@router.get("/trips/{trip_id}/alerts/active", response_model=List[AlertResponse])
def list_active_trip_alerts_endpoint(
    trip: Trip = Depends(require_trip_member),
    db: Session = Depends(get_db),
):
    """ACTIVE or ACKNOWLEDGED (not yet resolved)."""
    rows = alerts_service.list_active_alerts(db, trip.id)
    return [_serialize(a) for a in rows]


@router.get("/alerts/{alert_id}", response_model=AlertResponse)
def get_alert_endpoint(alert: Alert = Depends(require_alert_member)):
    return _serialize(alert)


@router.post("/alerts/{alert_id}/acknowledge", response_model=AlertResponse)
async def acknowledge_alert_endpoint(
    alert: Alert = Depends(require_alert_member),
    db: Session = Depends(get_db),
):
    updated = await run_in_threadpool(alerts_service.acknowledge_alert, db, alert)
    await _publish_alert_updated(updated)
    return _serialize(updated)


@router.post("/alerts/{alert_id}/resolve", response_model=AlertResponse)
async def resolve_alert_endpoint(
    alert: Alert = Depends(require_alert_member),
    db: Session = Depends(get_db),
):
    updated = await run_in_threadpool(alerts_service.resolve_alert, db, alert)
    await _publish_alert_updated(updated)
    return _serialize(updated)
