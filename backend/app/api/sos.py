import uuid
from typing import List, Optional

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.core.errors import AppHTTPException
from app.core.rate_limit import rate_limit_by_user
from app.core.redis import get_redis
from app.dependencies.auth import get_current_user_id
from app.dependencies.sos import require_sos_member
from app.dependencies.trip import require_trip_member
from app.models.enums import SOSStatus, TripStatus
from app.models.sos_event import SOSEvent
from app.models.trip import Trip
from app.schemas.sos import DEFAULT_SOS_LIMIT, MAX_SOS_LIMIT, SOSCreate, SOSResponse
from app.sos import service as sos_service

router = APIRouter(tags=["SOS"])


def _serialize(sos: SOSEvent) -> SOSResponse:
    return SOSResponse(
        id=sos.id,
        trip_id=sos.trip_id,
        user_id=sos.user_id,
        latitude=sos.latitude,
        longitude=sos.longitude,
        accuracy=sos.accuracy,
        message=sos.message,
        status=sos.status,
        metadata=sos.sos_metadata,
        triggered_at=sos.triggered_at,
        acknowledged_at=sos.acknowledged_at,
        resolved_at=sos.resolved_at,
        created_at=sos.created_at,
    )


def _get_redis_or_none():
    try:
        return get_redis()
    except RuntimeError:
        return None


@router.post(
    "/trips/{trip_id}/sos",
    response_model=SOSResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(rate_limit_by_user("sos", lambda: settings.SOS_RATE_LIMIT_PER_MINUTE))],
)
async def trigger_sos_endpoint(
    data: SOSCreate,
    user_id: str = Depends(get_current_user_id),
    trip: Trip = Depends(require_trip_member),
    db: Session = Depends(get_db),
):
    """User-triggered emergency. user_id/group_id/trip_id are never taken
    from the request body — trip_id from the URL (already authorized by
    require_trip_member), group_id from the trip, user_id from the
    verified JWT.

    Rate-limited (SOS_RATE_LIMIT_PER_MINUTE) but deliberately not
    aggressively so — the real protection against accidental/duplicate
    emergencies is sos_service.trigger_sos's own idempotency check (an
    already-ACTIVE SOS for this user/trip is returned as-is, never
    duplicated), not this limit. This limit only guards against a
    distinct trigger/cancel/retrigger abuse loop, and never blocks the
    first, genuine call."""
    if trip.status != TripStatus.ACTIVE:
        raise AppHTTPException(
            status_code=409, code="TRIP_NOT_ACTIVE", detail="SOS can only be triggered on an active trip."
        )

    redis = _get_redis_or_none()
    sos = await sos_service.trigger_sos(db, redis, trip.id, trip.group_id, uuid.UUID(user_id), data)
    return _serialize(sos)


@router.get("/trips/{trip_id}/sos", response_model=List[SOSResponse])
def list_trip_sos_endpoint(
    trip: Trip = Depends(require_trip_member),
    db: Session = Depends(get_db),
    status_filter: Optional[SOSStatus] = Query(None, alias="status"),
    limit: int = Query(DEFAULT_SOS_LIMIT, ge=1, le=MAX_SOS_LIMIT),
):
    """Full SOS history for the trip, newest first."""
    rows = sos_service.list_sos(db, trip.id, status=status_filter, limit=limit)
    return [_serialize(s) for s in rows]


@router.get("/trips/{trip_id}/sos/active", response_model=List[SOSResponse])
def list_active_trip_sos_endpoint(
    trip: Trip = Depends(require_trip_member),
    db: Session = Depends(get_db),
):
    """ACTIVE or ACKNOWLEDGED (not yet resolved/cancelled)."""
    rows = sos_service.list_active_sos(db, trip.id)
    return [_serialize(s) for s in rows]


@router.post("/sos/{sos_id}/acknowledge", response_model=SOSResponse)
async def acknowledge_sos_endpoint(
    sos: SOSEvent = Depends(require_sos_member),
    db: Session = Depends(get_db),
):
    updated = await sos_service.acknowledge_sos(db, _get_redis_or_none(), sos)
    return _serialize(updated)


@router.post("/sos/{sos_id}/resolve", response_model=SOSResponse)
async def resolve_sos_endpoint(
    sos: SOSEvent = Depends(require_sos_member),
    db: Session = Depends(get_db),
):
    updated = await sos_service.resolve_sos(db, _get_redis_or_none(), sos)
    return _serialize(updated)


@router.post("/sos/{sos_id}/cancel", response_model=SOSResponse)
async def cancel_sos_endpoint(
    user_id: str = Depends(get_current_user_id),
    sos: SOSEvent = Depends(require_sos_member),
    db: Session = Depends(get_db),
):
    """Only the person who triggered this SOS may cancel it — enforced in
    the service layer, never trusted from any client-supplied field."""
    updated = await sos_service.cancel_sos(db, _get_redis_or_none(), sos, uuid.UUID(user_id))
    return _serialize(updated)
