"""Trip history — GET /users/me/trips, GET /groups/{group_id}/trips.

"Participated"/"belongs to this group" is scoped the same way every other
trip-scoped endpoint in this API scopes membership: the authenticated
user (or, for group history, anyone asking) must be a currently ACTIVE
member of the trip's group — see require_trip_member /
require_group_member elsewhere in this codebase. A user who has since
left a group stops seeing that group's trip history, consistent with
every other endpoint's authorization model; this is a documented scope
choice, not an oversight (see the backend README).
"""

import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.analytics import queries
from app.analytics.snapshot import get_snapshot
from app.core.config import settings
from app.models.enums import MemberStatus, TripStatus
from app.models.group_member import GroupMember
from app.models.trip import Trip
from app.schemas.analytics import TripHistoryItem, TripHistoryResponse


def _apply_filters(stmt, *, status: Optional[TripStatus], from_time: Optional[datetime], to_time: Optional[datetime]):
    if status is not None:
        stmt = stmt.where(Trip.status == status)
    if from_time is not None:
        stmt = stmt.where(Trip.created_at >= from_time)
    if to_time is not None:
        stmt = stmt.where(Trip.created_at <= to_time)
    return stmt


def _distance_for_history_item(db: Session, trip: Trip) -> Optional[float]:
    """Prefers the immutable snapshot for a COMPLETED trip (an O(1) read
    instead of re-scanning that trip's location_history on every page of
    every history request) and only recomputes live when there isn't one
    (a non-COMPLETED trip, or a COMPLETED trip that predates snapshot
    generation)."""
    if trip.status == TripStatus.COMPLETED:
        snapshot = get_snapshot(db, trip.id)
        if snapshot is not None:
            return snapshot.distance_traveled_meters

    points_by_user = queries.fetch_location_points(db, trip.id)
    if not points_by_user:
        return None
    distances = queries.compute_distances_by_user(
        points_by_user, max_speed_mps=settings.MAX_ANALYTICS_SPEED_MPS, max_accuracy_meters=settings.MIN_USABLE_ACCURACY_METERS
    )
    leader_id = queries.get_group_leader_id(db, trip.group_id)
    return queries.pick_representative_value(distances, leader_id)


def _serialize(db: Session, trip: Trip) -> TripHistoryItem:
    member_count = len(queries.list_active_group_members(db, trip.group_id))
    distance = _distance_for_history_item(db, trip)
    return TripHistoryItem(
        trip_id=trip.id,
        name=trip.destination_name,
        status=trip.status.value,
        started_at=trip.started_at,
        ended_at=trip.ended_at,
        member_count=member_count,
        distance_meters=round(distance) if distance is not None else None,
    )


def _paginate(
    db: Session,
    base_stmt,
    *,
    status: Optional[TripStatus],
    from_time: Optional[datetime],
    to_time: Optional[datetime],
    limit: int,
    offset: int,
) -> TripHistoryResponse:
    filtered = _apply_filters(base_stmt, status=status, from_time=from_time, to_time=to_time)

    total = db.scalar(select(func.count()).select_from(filtered.subquery())) or 0
    rows = db.scalars(filtered.order_by(Trip.created_at.desc()).limit(limit).offset(offset)).all()
    items = [_serialize(db, trip) for trip in rows]
    return TripHistoryResponse(items=items, total=total, limit=limit, offset=offset)


def list_user_trip_history(
    db: Session,
    user_id: uuid.UUID,
    *,
    status: Optional[TripStatus] = None,
    from_time: Optional[datetime] = None,
    to_time: Optional[datetime] = None,
    limit: int,
    offset: int,
) -> TripHistoryResponse:
    member_group_ids = select(GroupMember.group_id).where(
        GroupMember.user_id == user_id, GroupMember.status == MemberStatus.ACTIVE
    )
    base_stmt = select(Trip).where(Trip.group_id.in_(member_group_ids))
    return _paginate(db, base_stmt, status=status, from_time=from_time, to_time=to_time, limit=limit, offset=offset)


def list_group_trip_history(
    db: Session,
    group_id: uuid.UUID,
    *,
    status: Optional[TripStatus] = None,
    from_time: Optional[datetime] = None,
    to_time: Optional[datetime] = None,
    limit: int,
    offset: int,
) -> TripHistoryResponse:
    base_stmt = select(Trip).where(Trip.group_id == group_id)
    return _paginate(db, base_stmt, status=status, from_time=from_time, to_time=to_time, limit=limit, offset=offset)
