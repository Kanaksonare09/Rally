"""
Trip lifecycle business logic. Routers only authenticate, validate the
request, call these functions, and return the result.

State machine:

    CREATED -> ACTIVE -> COMPLETED
    CREATED -> CANCELLED

Every other transition is rejected by _require_transition() with a 409
INVALID_TRIP_STATE. "At most one ACTIVE trip per group" is enforced twice:
an app-level pre-check here (fast, friendly error on the common path) and a
partial unique index in the database (see migration 0002 — the actual
guarantee against a race between two concurrent start requests).
"""

import uuid
from datetime import datetime, timezone
from typing import List, Optional

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.errors import AppHTTPException
from app.models.enums import TripStatus
from app.models.trip import Trip
from app.schemas.trip import TripCreate, TripStart

_ALLOWED_TRANSITIONS = {
    TripStatus.CREATED: {TripStatus.ACTIVE, TripStatus.CANCELLED},
    TripStatus.ACTIVE: {TripStatus.COMPLETED},
    TripStatus.COMPLETED: set(),
    TripStatus.CANCELLED: set(),
}


def _require_transition(trip: Trip, target: TripStatus) -> None:
    allowed = _ALLOWED_TRANSITIONS.get(trip.status, set())
    if target not in allowed:
        raise AppHTTPException(
            status_code=409,
            code="INVALID_TRIP_STATE",
            detail=f"Cannot move a trip from {trip.status.value} to {target.value}.",
        )


def _point_wkt(latitude: Optional[float], longitude: Optional[float]) -> Optional[str]:
    """Pydantic already range-validates lat/lon individually; this catches
    the case where only one of the pair was supplied."""
    if latitude is None and longitude is None:
        return None
    if latitude is None or longitude is None:
        raise AppHTTPException(
            status_code=400,
            code="INVALID_LOCATION",
            detail="Both latitude and longitude are required together.",
        )
    return f"POINT({longitude} {latitude})"


from app.services.profile_service import get_or_create_profile


def create_trip(db: Session, group_id: uuid.UUID, user_id: uuid.UUID, data: TripCreate) -> Trip:
    get_or_create_profile(db, str(user_id))
    destination = _point_wkt(data.latitude, data.longitude)
    trip = Trip(
        group_id=group_id,
        started_by=user_id,
        status=TripStatus.CREATED,
        destination_name=data.destination_name,
        destination=destination,
    )
    db.add(trip)
    db.commit()
    db.refresh(trip)
    return trip


def list_group_trips(db: Session, group_id: uuid.UUID) -> List[Trip]:
    stmt = select(Trip).where(Trip.group_id == group_id).order_by(Trip.created_at.desc())
    return list(db.scalars(stmt).all())


def get_trip_by_id(db: Session, trip_id: uuid.UUID) -> Optional[Trip]:
    return db.get(Trip, trip_id)


def _has_other_active_trip(db: Session, group_id: uuid.UUID, exclude_trip_id: uuid.UUID) -> bool:
    stmt = select(Trip).where(
        Trip.group_id == group_id,
        Trip.status == TripStatus.ACTIVE,
        Trip.id != exclude_trip_id,
    )
    return db.scalars(stmt).first() is not None


def start_trip(db: Session, trip: Trip, data: Optional[TripStart]) -> Trip:
    _require_transition(trip, TripStatus.ACTIVE)

    if _has_other_active_trip(db, trip.group_id, trip.id):
        raise AppHTTPException(
            status_code=409,
            code="ACTIVE_TRIP_EXISTS",
            detail="This group already has an active trip.",
        )

    if data is not None:
        trip.start_location = _point_wkt(data.latitude, data.longitude)

    trip.status = TripStatus.ACTIVE
    trip.started_at = datetime.now(timezone.utc)

    try:
        db.commit()
    except IntegrityError as exc:
        # The app-level check above closes the common-case window, but only
        # the database's partial unique index is safe against two requests
        # racing past that check at the same time.
        db.rollback()
        raise AppHTTPException(
            status_code=409,
            code="ACTIVE_TRIP_EXISTS",
            detail="This group already has an active trip.",
        ) from exc

    db.refresh(trip)
    return trip


def end_trip(db: Session, trip: Trip) -> Trip:
    _require_transition(trip, TripStatus.COMPLETED)
    trip.status = TripStatus.COMPLETED
    trip.ended_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(trip)
    return trip


def cancel_trip(db: Session, trip: Trip) -> Trip:
    _require_transition(trip, TripStatus.CANCELLED)
    trip.status = TripStatus.CANCELLED
    db.commit()
    db.refresh(trip)
    return trip
