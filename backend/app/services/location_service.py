"""
GPS ingestion business logic. Routers only authenticate, validate the
request shape, call these functions, and return the result.

Ingestion path is deliberately simple (auth -> authorize -> validate ->
insert -> return) — no route/deviation/risk calculations here, those
belong to a later intelligence phase. Redis-backed rate limiting isn't
implemented yet either; record_location() takes a single (trip, user_id,
data) call so a rate limiter can wrap it later without restructuring
anything.
"""

import uuid
from datetime import datetime, timedelta, timezone
from typing import List, Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import AppHTTPException
from app.models.enums import TripStatus
from app.models.location_history import LocationHistory
from app.models.trip import Trip
from app.schemas.location import LocationCreate, LocationHistoryQuery

# Mobile clocks drift; this is generous enough to absorb normal drift while
# still catching a genuinely wrong/garbage device clock.
MAX_FUTURE_DRIFT = timedelta(minutes=5)


def _point_wkt(latitude: float, longitude: float) -> str:
    return f"POINT({longitude} {latitude})"


def _normalize_recorded_at(recorded_at: Optional[datetime]) -> datetime:
    """recorded_at = when the device captured the reading (may arrive out
    of order); created_at = when the backend stored it. Only the former is
    normalized/validated here — the latter is a plain server-side default."""
    now = datetime.now(timezone.utc)
    if recorded_at is None:
        return now

    normalized = recorded_at if recorded_at.tzinfo is not None else recorded_at.replace(tzinfo=timezone.utc)
    normalized = normalized.astimezone(timezone.utc)

    if normalized > now + MAX_FUTURE_DRIFT:
        raise AppHTTPException(
            status_code=400,
            code="INVALID_TIMESTAMP",
            detail="recorded_at cannot be significantly in the future.",
        )
    return normalized


def record_location(db: Session, trip: Trip, user_id: uuid.UUID, data: LocationCreate) -> LocationHistory:
    if trip.status != TripStatus.ACTIVE:
        raise AppHTTPException(
            status_code=409,
            code="INVALID_TRIP_STATE",
            detail="Location can only be submitted for an active trip.",
        )

    recorded_at = _normalize_recorded_at(data.recorded_at)

    location = LocationHistory(
        trip_id=trip.id,
        group_id=trip.group_id,  # derived from the trip, never from the request
        user_id=user_id,  # derived from the verified token, never from the request
        location=_point_wkt(data.latitude, data.longitude),
        latitude=data.latitude,
        longitude=data.longitude,
        accuracy=data.accuracy,
        speed=data.speed,
        heading=data.heading,
        recorded_at=recorded_at,
    )
    db.add(location)
    db.commit()
    db.refresh(location)
    return location


def get_location_history(db: Session, trip_id: uuid.UUID, query: LocationHistoryQuery) -> List[LocationHistory]:
    stmt = select(LocationHistory).where(LocationHistory.trip_id == trip_id)

    if query.user_id is not None:
        # Naturally scoped to this trip already — a user_id with no
        # locations on this trip (an outsider, or a member of a different
        # group) just yields an empty result, never another group's data.
        stmt = stmt.where(LocationHistory.user_id == query.user_id)
    if query.from_time is not None:
        stmt = stmt.where(LocationHistory.recorded_at >= query.from_time)
    if query.to_time is not None:
        stmt = stmt.where(LocationHistory.recorded_at <= query.to_time)
    if query.cursor is not None:
        stmt = stmt.where(LocationHistory.recorded_at > query.cursor)

    stmt = stmt.order_by(LocationHistory.recorded_at.asc()).limit(query.limit)
    return list(db.scalars(stmt).all())
