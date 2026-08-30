"""
Deterministic demo data: a fixed demo group, 4 fixed demo members, and a
fixed demo route — all identified by UUIDs derived from a constant
namespace (uuid5), so "the demo group" is always the exact same row
across every reset, never a randomly-generated new one. Every demo
control endpoint (app/api/demo.py) operates ONLY on these fixed ids —
never a group/trip id taken from the request — which is what makes it
safe for demo endpoints to have no per-call authorization check of their
own: there is no arbitrary id a caller could substitute to reach real
user data.

No real personal information: demo member names are plainly fictional
placeholders, not modeled on any real person.
"""

import logging
import uuid
from typing import List

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from app.models.auth_shadow import auth_users
from app.models.enums import GroupStatus, MemberRole, MemberStatus, TripStatus
from app.models.group import Group
from app.models.group_member import GroupMember
from app.models.profile import Profile
from app.models.trip import Trip
from app.route import service as route_service
from app.schemas.route import RouteCreate
from app.schemas.trip import TripCreate
from app.services import trip_service

logger = logging.getLogger("rally.demo")

_NAMESPACE = uuid.UUID("6ba7b810-9dad-11d1-80b4-00c04fd430c8")  # fixed, arbitrary — any constant UUID works as a uuid5 namespace

DEMO_GROUP_ID = uuid.uuid5(_NAMESPACE, "rally-demo-group")
DEMO_USER_IDS: List[uuid.UUID] = [uuid.uuid5(_NAMESPACE, f"rally-demo-member-{i}") for i in range(4)]
DEMO_USER_NAMES = ["Asha Patel", "Rohan Verma", "Meera Iyer", "Kabir Shah"]
DEMO_LEADER_ID = DEMO_USER_IDS[0]

# A simple ~5.5km path (near Indore, MI — the same demo coordinates used
# elsewhere in this codebase's own examples), with a gentle bend so a
# route-deviation scenario has somewhere meaningful to deviate from.
DEMO_ROUTE_COORDINATES = [
    [75.8577, 22.7196],
    [75.8590, 22.7220],
    [75.8610, 22.7255],
    [75.8630, 22.7290],
    [75.8660, 22.7320],
    [75.8700, 22.7345],
    [75.8740, 22.7360],
]
DEMO_ROUTE_ORIGIN = (DEMO_ROUTE_COORDINATES[0][1], DEMO_ROUTE_COORDINATES[0][0])  # (lat, lon)
DEMO_ROUTE_DESTINATION = (DEMO_ROUTE_COORDINATES[-1][1], DEMO_ROUTE_COORDINATES[-1][0])


def _ensure_demo_identity_sync(db: Session, user_id: uuid.UUID, full_name: str) -> None:
    """Demo members aren't real Supabase-authenticated users, so there's
    no signup flow to create their auth.users/profiles rows the normal
    way (see app/services/profile_service.py) — this inserts them
    directly, idempotently (ON CONFLICT DO NOTHING), which is acceptable
    ONLY because this whole module is unreachable unless DEMO_MODE=true,
    which is itself refused together with ENVIRONMENT=production at
    startup (see app/core/config.py)."""
    db.execute(pg_insert(auth_users).values(id=user_id).on_conflict_do_nothing(index_elements=["id"]))
    profile = db.get(Profile, user_id)
    if profile is None:
        db.add(Profile(id=user_id, full_name=full_name))


def ensure_demo_group_sync(db: Session) -> Group:
    """Get-or-create the one fixed demo group, its 4 fixed members, and
    their identity rows. Safe to call repeatedly — a second call is a
    cheap no-op once everything already exists."""
    group = db.get(Group, DEMO_GROUP_ID)
    if group is not None:
        return group

    for user_id, name in zip(DEMO_USER_IDS, DEMO_USER_NAMES):
        _ensure_demo_identity_sync(db, user_id, name)

    group = Group(
        id=DEMO_GROUP_ID, name="RALLY Demo Squad", join_code="RALLYDEMO", leader_id=DEMO_LEADER_ID,
        destination_name="Demo Ride", status=GroupStatus.ACTIVE,
    )
    db.add(group)
    db.flush()

    for i, user_id in enumerate(DEMO_USER_IDS):
        db.add(
            GroupMember(
                group_id=group.id, user_id=user_id,
                role=MemberRole.LEADER if user_id == DEMO_LEADER_ID else MemberRole.MEMBER,
                status=MemberStatus.ACTIVE,
            )
        )

    db.commit()
    db.refresh(group)
    logger.info("Demo group created: group_id=%s", group.id)
    return group


def get_active_demo_trip_sync(db: Session) -> Trip:
    return db.scalars(
        select(Trip).where(Trip.group_id == DEMO_GROUP_ID, Trip.status == TripStatus.ACTIVE)
    ).first()


def end_active_demo_trip_sync(db: Session) -> None:
    """Cleanly ends whatever demo trip is currently ACTIVE, if any — used
    by both /demo/reset and starting a new scenario (only one ACTIVE trip
    per group is ever allowed, same rule as every real group)."""
    trip = get_active_demo_trip_sync(db)
    if trip is None:
        return
    trip_service.end_trip(db, trip)
    route_service.complete_route_sync(db, trip.id)


def create_and_start_demo_trip_sync(db: Session) -> Trip:
    """Creates a fresh demo trip + route (Phase 9's own leader-only
    creation path — the demo leader is the one "creating" it, exactly
    like a real trip) and starts it. Ends any already-ACTIVE demo trip
    first."""
    group = ensure_demo_group_sync(db)
    end_active_demo_trip_sync(db)

    trip = trip_service.create_trip(db, group.id, DEMO_LEADER_ID, TripCreate(destination_name="Demo Ride"))
    route_service.create_or_replace_route(
        db, trip,
        RouteCreate(
            name="Demo Route",
            origin_latitude=DEMO_ROUTE_ORIGIN[0], origin_longitude=DEMO_ROUTE_ORIGIN[1],
            destination_latitude=DEMO_ROUTE_DESTINATION[0], destination_longitude=DEMO_ROUTE_DESTINATION[1],
            coordinates=DEMO_ROUTE_COORDINATES,
        ),
    )
    trip = trip_service.start_trip(db, trip, None)
    route_service.activate_route_sync(db, trip.id)
    logger.info("Demo trip started: trip_id=%s", trip.id)
    return trip


def reset_demo_sync(db: Session) -> Group:
    """POST /demo/reset: ends any running demo trip, leaves the demo
    group/members/history in place (they're the reusable fixture, not
    per-scenario state — only the trip is per-scenario)."""
    group = ensure_demo_group_sync(db)
    end_active_demo_trip_sync(db)
    return group
