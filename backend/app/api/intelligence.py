import uuid
from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.errors import AppHTTPException
from app.core.redis import get_redis
from app.dependencies.trip import require_trip_member
from app.intelligence import engine, events
from app.models.enums import IntelligenceEventType, IntelligenceSeverity
from app.models.trip import Trip
from app.schemas.intelligence import (
    DEFAULT_INTELLIGENCE_EVENTS_LIMIT,
    MAX_INTELLIGENCE_EVENTS_LIMIT,
    IntelligenceEventQuery,
    IntelligenceEventResponse,
    MemberIntelligenceState,
    TripIntelligenceResponse,
)

router = APIRouter(tags=["Intelligence"])


def _serialize_event(event) -> IntelligenceEventResponse:
    return IntelligenceEventResponse(
        id=event.id,
        trip_id=event.trip_id,
        event_type=event.event_type,
        severity=event.severity,
        user_id=event.user_id,
        related_user_id=event.related_user_id,
        detected_at=event.detected_at,
        resolved_at=event.resolved_at,
        metadata=event.event_metadata,
    )


@router.get("/trips/{trip_id}/intelligence", response_model=TripIntelligenceResponse)
async def get_trip_intelligence_endpoint(
    trip: Trip = Depends(require_trip_member),
    db: Session = Depends(get_db),
):
    """Current calculated state — live Redis data plus the same detector
    logic the background worker uses, never a location_history scan. See
    app/intelligence/engine.py."""
    try:
        redis = get_redis()
    except RuntimeError as exc:
        raise AppHTTPException(
            status_code=503, code="SERVICE_UNAVAILABLE", detail="Live intelligence is temporarily unavailable."
        ) from exc

    computed = await engine.compute_current_state(db, redis, trip.id, trip.group_id)
    active_events = events.list_active_events(db, trip.id)

    return TripIntelligenceResponse(
        trip_id=trip.id,
        group_state=computed.group_state,
        members=[
            MemberIntelligenceState(
                user_id=m.user_id,
                name=m.name,
                role=m.role,
                movement_state=m.movement_state,
                presence=m.presence,
                location_age_seconds=m.location_age_seconds,
                latitude=m.latitude,
                longitude=m.longitude,
                speed=m.speed,
                distance_from_group_center_meters=m.distance_from_group_center_meters,
                is_isolated=m.is_isolated,
                is_falling_behind=m.is_falling_behind,
            )
            for m in computed.members
        ],
        active_events=[_serialize_event(e) for e in active_events],
    )


@router.get("/trips/{trip_id}/intelligence-events", response_model=List[IntelligenceEventResponse])
def get_trip_intelligence_events_endpoint(
    trip: Trip = Depends(require_trip_member),
    db: Session = Depends(get_db),
    event_type: Optional[IntelligenceEventType] = Query(None),
    severity: Optional[IntelligenceSeverity] = Query(None),
    user_id: Optional[uuid.UUID] = Query(None),
    active_only: bool = Query(False),
    from_: Optional[datetime] = Query(None, alias="from"),
    to: Optional[datetime] = Query(None),
    limit: int = Query(DEFAULT_INTELLIGENCE_EVENTS_LIMIT, ge=1, le=MAX_INTELLIGENCE_EVENTS_LIMIT),
):
    """Historical detections for this trip, newest first. Always scoped
    to the one trip in the URL — never cross-trip, regardless of filters."""
    query = IntelligenceEventQuery(
        event_type=event_type,
        severity=severity,
        user_id=user_id,
        active_only=active_only,
        from_time=from_,
        to_time=to,
        limit=limit,
    )
    rows = events.list_events(
        db,
        trip.id,
        event_type=query.event_type,
        severity=query.severity,
        user_id=query.user_id,
        active_only=query.active_only,
        from_time=query.from_time,
        to_time=query.to_time,
        limit=query.limit,
    )
    return [_serialize_event(e) for e in rows]
