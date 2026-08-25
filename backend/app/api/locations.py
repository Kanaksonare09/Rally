import uuid
from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.dependencies.auth import get_current_user_id
from app.dependencies.trip import require_trip_member
from app.models.trip import Trip
from app.schemas.location import (
    DEFAULT_LOCATION_HISTORY_LIMIT,
    MAX_LOCATION_HISTORY_LIMIT,
    LocationCreate,
    LocationHistoryItem,
    LocationHistoryQuery,
    LocationResponse,
)
from app.services import location_service

router = APIRouter(tags=["Locations"])


@router.post("/trips/{trip_id}/locations", response_model=LocationResponse, status_code=status.HTTP_201_CREATED)
def submit_location_endpoint(
    data: LocationCreate,
    trip: Trip = Depends(require_trip_member),
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    """Record one GPS reading. Requires an active member of the trip's
    group, and the trip must currently be ACTIVE."""
    return location_service.record_location(db, trip, uuid.UUID(user_id), data)


@router.get("/trips/{trip_id}/locations", response_model=List[LocationHistoryItem])
def get_location_history_endpoint(
    trip: Trip = Depends(require_trip_member),
    db: Session = Depends(get_db),
    from_: Optional[datetime] = Query(None, alias="from", description="Only points at/after this recorded_at."),
    to: Optional[datetime] = Query(None, description="Only points at/before this recorded_at."),
    user_id: Optional[uuid.UUID] = Query(None, description="Restrict to one group member's points."),
    limit: int = Query(DEFAULT_LOCATION_HISTORY_LIMIT, ge=1, le=MAX_LOCATION_HISTORY_LIMIT),
    cursor: Optional[datetime] = Query(
        None, description="Return only points after this recorded_at (use the last point's recorded_at to page forward)."
    ),
):
    """Chronological (recorded_at ASC) GPS history for the trip. Requires
    an active member of the trip's group — works for any trip status, since
    this also serves a completed trip's history."""
    query = LocationHistoryQuery(from_time=from_, to_time=to, user_id=user_id, limit=limit, cursor=cursor)
    return location_service.get_location_history(db, trip.id, query)
