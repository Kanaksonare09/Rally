import uuid
from typing import List, Optional

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.dependencies.auth import get_current_user_id
from app.dependencies.group import require_group_member
from app.dependencies.trip import require_trip_creator_or_leader, require_trip_member
from app.models.group_member import GroupMember
from app.models.trip import Trip
from app.schemas.trip import TripCreate, TripListItem, TripResponse, TripStart
from app.services import trip_service

router = APIRouter(tags=["Trips"])


@router.post("/groups/{group_id}/trips", response_model=TripResponse, status_code=status.HTTP_201_CREATED)
def create_trip_endpoint(
    group_id: uuid.UUID,
    data: TripCreate,
    user_id: str = Depends(get_current_user_id),
    member: GroupMember = Depends(require_group_member),
    db: Session = Depends(get_db),
):
    """Create a trip in CREATED state. Any active group member may do this."""
    return trip_service.create_trip(db, group_id, uuid.UUID(user_id), data)


@router.get("/groups/{group_id}/trips", response_model=List[TripListItem])
def list_group_trips_endpoint(
    group_id: uuid.UUID,
    member: GroupMember = Depends(require_group_member),
    db: Session = Depends(get_db),
):
    """List the group's trips, newest first. Must be an active member."""
    return trip_service.list_group_trips(db, group_id)


@router.get("/trips/{trip_id}", response_model=TripResponse)
def get_trip_endpoint(trip: Trip = Depends(require_trip_member)):
    return trip


@router.post("/trips/{trip_id}/start", response_model=TripResponse)
def start_trip_endpoint(
    data: Optional[TripStart] = None,
    trip: Trip = Depends(require_trip_member),
    db: Session = Depends(get_db),
):
    """CREATED -> ACTIVE. Rejected with 409 if the group already has
    another active trip, or if this trip isn't CREATED."""
    return trip_service.start_trip(db, trip, data)


@router.post("/trips/{trip_id}/end", response_model=TripResponse)
def end_trip_endpoint(
    trip: Trip = Depends(require_trip_member),
    db: Session = Depends(get_db),
):
    """ACTIVE -> COMPLETED."""
    return trip_service.end_trip(db, trip)


@router.post("/trips/{trip_id}/cancel", response_model=TripResponse)
def cancel_trip_endpoint(
    trip: Trip = Depends(require_trip_creator_or_leader),
    db: Session = Depends(get_db),
):
    """CREATED -> CANCELLED. Only the trip's creator or the group leader."""
    return trip_service.cancel_trip(db, trip)
