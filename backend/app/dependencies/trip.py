"""
Trip authorization chain, mirroring app/dependencies/group.py:

    trip_id -> get_trip_or_404() -> get_trip_membership()
        -> require_trip_member() / require_trip_creator_or_leader()

A trip that doesn't exist and a trip whose group the caller doesn't
actively belong to return the same 404 TRIP_NOT_FOUND — same
existence-hiding rationale as require_group_member().
"""

import uuid
from typing import Tuple

from fastapi import Depends, HTTPException, Path, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.errors import AppHTTPException
from app.dependencies.auth import get_current_user_id
from app.models.enums import MemberRole, MemberStatus
from app.models.group_member import GroupMember
from app.models.trip import Trip
from app.services import trip_service


def get_trip_or_404(trip_id: uuid.UUID = Path(...), db: Session = Depends(get_db)) -> Trip:
    trip = trip_service.get_trip_by_id(db, trip_id)
    if not trip:
        raise AppHTTPException(status_code=status.HTTP_404_NOT_FOUND, code="TRIP_NOT_FOUND", detail="Trip not found.")
    return trip


def get_trip_membership(
    # user_id resolved first: an unauthenticated request must fail with 401
    # before ever touching the database, not after a trip lookup runs.
    user_id: str = Depends(get_current_user_id),
    trip: Trip = Depends(get_trip_or_404),
    db: Session = Depends(get_db),
) -> Tuple[Trip, GroupMember]:
    member = db.scalars(
        select(GroupMember).where(
            GroupMember.group_id == trip.group_id, GroupMember.user_id == user_id
        )
    ).first()

    if not member or member.status != MemberStatus.ACTIVE:
        raise AppHTTPException(status_code=status.HTTP_404_NOT_FOUND, code="TRIP_NOT_FOUND", detail="Trip not found.")

    return trip, member


def require_trip_member(pair: Tuple[Trip, GroupMember] = Depends(get_trip_membership)) -> Trip:
    trip, _member = pair
    return trip


def require_trip_creator_or_leader(pair: Tuple[Trip, GroupMember] = Depends(get_trip_membership)) -> Trip:
    trip, member = pair
    is_creator = trip.started_by is not None and str(trip.started_by) == str(member.user_id)
    is_leader = member.role == MemberRole.LEADER
    if not (is_creator or is_leader):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only the trip creator or the group leader can perform this action.",
        )
    return trip
