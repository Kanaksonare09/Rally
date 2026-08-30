"""
Route CRUD/lifecycle (Postgres) plus the live per-tick progress computation
that ties a route's geometry to members' current locations (Redis, via
app/route/matcher.py + app/route/progress.py). Mirrors the shape of
app/alerts/service.py: sync DB helpers wrapped in run_in_threadpool by the
handful of async entry points callers actually use.

Kept independent of app/intelligence/ and app/websocket/, same rule
engine.py documents for itself — this module has no idea WebSockets exist.
app/intelligence/engine.py is the one place that calls into both this
module and the WebSocket layer, exactly as it already does for
app/alerts/service.py.
"""

import json
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple

from redis.asyncio import Redis
from sqlalchemy import select
from sqlalchemy.orm import Session
from starlette.concurrency import run_in_threadpool

from app.core.errors import AppHTTPException
from app.core.redis_keys import route_progress_key
from app.intelligence.distance import haversine_distance_meters
from app.intelligence.thresholds import Thresholds, current_thresholds
from app.models.enums import MemberStatus, RouteStatus, TripStatus
from app.models.group_member import GroupMember
from app.models.profile import Profile
from app.models.route import Route
from app.models.trip import Trip
from app.route import progress as route_progress
from app.route.eta import EtaResult, EtaService
from app.route.matcher import RouteGeometry, RouteMatch, build_route_geometry, match_point_to_route
from app.schemas.route import RouteCreate
from app.services import live_state_service, presence_service


def _linestring_wkt(coordinates: List[Tuple[float, float]]) -> str:
    pairs = ", ".join(f"{lon} {lat}" for lon, lat in coordinates)
    return f"LINESTRING({pairs})"


def get_route_by_trip(db: Session, trip_id: uuid.UUID) -> Optional[Route]:
    return db.scalars(select(Route).where(Route.trip_id == trip_id)).first()


def _validate_endpoints(data: RouteCreate, geometry: RouteGeometry, thresholds: Thresholds) -> None:
    """Routing geometry rarely begins/ends at an exact coordinate match
    with the caller's declared origin/destination (rounding, snapping to a
    road network, etc.) — ROUTE_ENDPOINT_TOLERANCE_METERS is how far apart
    they're allowed to be before this is treated as a mismatched/bogus
    request rather than the same trip."""
    first_lon, first_lat = geometry.coordinates[0]
    last_lon, last_lat = geometry.coordinates[-1]
    origin_gap = haversine_distance_meters(data.origin_latitude, data.origin_longitude, first_lat, first_lon)
    destination_gap = haversine_distance_meters(
        data.destination_latitude, data.destination_longitude, last_lat, last_lon
    )
    if origin_gap > thresholds.route_endpoint_tolerance_meters:
        raise AppHTTPException(
            status_code=400,
            code="INVALID_ROUTE_GEOMETRY",
            detail=(
                f"Declared origin is {origin_gap:.0f}m from the route geometry's first point "
                f"(tolerance {thresholds.route_endpoint_tolerance_meters:.0f}m)."
            ),
        )
    if destination_gap > thresholds.route_endpoint_tolerance_meters:
        raise AppHTTPException(
            status_code=400,
            code="INVALID_ROUTE_GEOMETRY",
            detail=(
                f"Declared destination is {destination_gap:.0f}m from the route geometry's last point "
                f"(tolerance {thresholds.route_endpoint_tolerance_meters:.0f}m)."
            ),
        )


def create_or_replace_route(db: Session, trip: Trip, data: RouteCreate) -> Route:
    """Leader-only is enforced by the require_trip_leader dependency at
    the API layer, not here. One route per trip (routes.trip_id is UNIQUE
    at the database level too) — "replace" updates the existing row in
    place rather than creating a new one; there is no route versioning in
    this phase.

    Only allowed while the trip is still CREATED: once a trip is ACTIVE,
    members may already be matching against this route's geometry, so
    silently changing it out from under live progress tracking is
    disallowed rather than half-supported."""
    if trip.status != TripStatus.CREATED:
        raise AppHTTPException(
            status_code=409,
            code="INVALID_TRIP_STATE",
            detail="A route can only be created or replaced while the trip is in CREATED state.",
        )

    thresholds = current_thresholds()
    try:
        geometry = build_route_geometry(data.coordinates)
    except ValueError as exc:
        raise AppHTTPException(status_code=400, code="INVALID_ROUTE_GEOMETRY", detail=str(exc)) from exc

    _validate_endpoints(data, geometry, thresholds)

    existing = get_route_by_trip(db, trip.id)
    if existing is not None and existing.status != RouteStatus.PLANNED:
        raise AppHTTPException(
            status_code=409,
            code="ROUTE_NOT_REPLACEABLE",
            detail=f"This trip's route is {existing.status.value}; only a PLANNED route can be replaced.",
        )

    route = existing if existing is not None else Route(trip_id=trip.id)
    if existing is None:
        db.add(route)

    route.name = data.name
    route.origin_latitude = data.origin_latitude
    route.origin_longitude = data.origin_longitude
    route.destination_latitude = data.destination_latitude
    route.destination_longitude = data.destination_longitude
    route.coordinates = [[float(c[0]), float(c[1])] for c in data.coordinates]
    route.geometry = _linestring_wkt(geometry.coordinates)
    # Server-authoritative: the Haversine sum over the same coordinates
    # PostGIS's ST_Length(geography) would measure, computed in Python so
    # it's both testable without a live database and identical to what a
    # live Postgres would report for this geometry.
    route.distance_meters = geometry.total_distance_meters
    route.estimated_duration_seconds = data.estimated_duration_seconds
    route.status = RouteStatus.PLANNED

    db.commit()
    db.refresh(route)
    return route


def _transition_route_sync(db: Session, trip_id: uuid.UUID, from_status: RouteStatus, to_status: RouteStatus) -> Optional[Route]:
    """No-op (returns the route unchanged, or None) if there's no route,
    or it isn't in the expected `from_status` — a trip with no planned
    route is completely valid, and every trip-lifecycle hook that calls
    this must tolerate that silently (see app/api/trips.py)."""
    route = get_route_by_trip(db, trip_id)
    if route is None or route.status != from_status:
        return route
    route.status = to_status
    db.commit()
    db.refresh(route)
    return route


def activate_route_sync(db: Session, trip_id: uuid.UUID) -> Optional[Route]:
    """PLANNED -> ACTIVE, called when the trip itself starts."""
    return _transition_route_sync(db, trip_id, RouteStatus.PLANNED, RouteStatus.ACTIVE)


def complete_route_sync(db: Session, trip_id: uuid.UUID) -> Optional[Route]:
    """ACTIVE -> COMPLETED, called when the trip itself ends."""
    return _transition_route_sync(db, trip_id, RouteStatus.ACTIVE, RouteStatus.COMPLETED)


def cancel_route_sync(db: Session, trip_id: uuid.UUID) -> Optional[Route]:
    """PLANNED -> CANCELLED, called when the trip itself is cancelled (a
    trip can only be cancelled while still CREATED, so its route — if any
    — is necessarily still PLANNED too)."""
    return _transition_route_sync(db, trip_id, RouteStatus.PLANNED, RouteStatus.CANCELLED)


# ---- Live progress -------------------------------------------------------


@dataclass
class MemberRouteProgress:
    user_id: str
    name: Optional[str]
    role: str
    presence: str
    location_age_seconds: Optional[float]
    match: Optional[RouteMatch]
    route_state: Optional[str]
    eta: Optional[EtaResult]


def _load_active_members_sync(db: Session, group_id: uuid.UUID) -> List[dict]:
    """Same query shape as app/intelligence/engine.py's own
    _load_active_members_sync — kept as a separate small copy rather than
    a cross-module import, per this module's independence rule (see the
    module docstring)."""
    rows = db.execute(
        select(GroupMember, Profile)
        .join(Profile, GroupMember.user_id == Profile.id)
        .where(GroupMember.group_id == group_id, GroupMember.status == MemberStatus.ACTIVE)
    ).all()
    return [
        {"user_id": member.user_id, "name": profile.full_name, "role": member.role.value}
        for member, profile in rows
    ]


async def compute_route_progress(
    redis: Redis,
    trip_id: uuid.UUID,
    route: Route,
    members: List[dict],
    live_locations: Dict[str, dict],
    online_status: Dict[str, bool],
    now: datetime,
) -> Tuple[List[MemberRouteProgress], Optional[float], bool]:
    """Matches every active member's current live location (already
    fetched by the caller — this never re-reads Redis for locations/
    presence itself) against the route geometry, classifies each member's
    route_state, computes a baseline ETA, and refreshes each member's
    route-progress cache key. Returns (per-member results, the group's
    median route_fraction, whether the whole trip has arrived).

    A member without a fresh-enough live location (offline, or a location
    older than ROUTE_PROGRESS_STALE_SECONDS) is included in the returned
    list with `match`/`route_state`/`eta` all None, and is excluded from
    both the group median and the trip-arrival check — matching this
    phase's "excluding OFFLINE/STALE members" requirement.

    Takes `trip_id` rather than a full Trip ORM object so
    app/intelligence/engine.py's per-tick call — which only ever has
    trip_id/group_id, never a loaded Trip — can call this directly instead
    of duplicating a Trip lookup it doesn't otherwise need.
    """
    thresholds = current_thresholds()
    geometry = build_route_geometry(route.coordinates)

    results: List[MemberRouteProgress] = []
    eligible_fractions: List[float] = []
    route_states: Dict[str, str] = {}
    eligible_user_ids: List[str] = []

    for member in members:
        uid_str = str(member["user_id"])
        location = live_locations.get(uid_str)
        online = online_status.get(uid_str, False)

        location_age_seconds: Optional[float] = None
        if location is not None:
            recorded_at = datetime.fromisoformat(location["recorded_at"])
            location_age_seconds = (now - recorded_at).total_seconds()

        usable = (
            online
            and location is not None
            and location_age_seconds is not None
            and location_age_seconds <= thresholds.route_progress_stale_seconds
        )

        match: Optional[RouteMatch] = None
        state: Optional[str] = None
        eta: Optional[EtaResult] = None

        if usable:
            match = match_point_to_route(geometry, location["latitude"], location["longitude"])
            confirmed_arrived = await route_progress.compute_confirmed_arrival(
                redis, trip_id, uid_str, match.distance_remaining_meters, thresholds, now
            )
            state = route_progress.classify_route_state(
                distance_from_route_meters=match.distance_from_route_meters,
                distance_remaining_meters=match.distance_remaining_meters,
                confirmed_arrived=confirmed_arrived,
                thresholds=thresholds,
            )
            eta = EtaService.calculate_eta(
                distance_remaining_meters=match.distance_remaining_meters,
                route_distance_meters=route.distance_meters,
                route_estimated_duration_seconds=route.estimated_duration_seconds,
                current_speed_mps=location.get("speed"),
                thresholds=thresholds,
            )

            eligible_fractions.append(match.route_fraction)
            route_states[uid_str] = state
            eligible_user_ids.append(uid_str)

            await redis.set(
                route_progress_key(trip_id, uid_str),
                json.dumps(
                    {
                        "route_fraction": match.route_fraction,
                        "distance_traveled_meters": match.distance_traveled_meters,
                        "distance_remaining_meters": match.distance_remaining_meters,
                        "distance_from_route_meters": match.distance_from_route_meters,
                        "route_state": state,
                        "eta_seconds": eta.eta_seconds if eta else None,
                        "updated_at": now.isoformat(),
                    }
                ),
                ex=thresholds.route_progress_stale_seconds,
            )

        results.append(
            MemberRouteProgress(
                user_id=uid_str,
                name=member["name"],
                role=member["role"],
                presence="ONLINE" if online else "OFFLINE",
                location_age_seconds=(round(location_age_seconds, 1) if location_age_seconds is not None else None),
                match=match,
                route_state=state,
                eta=eta,
            )
        )

    group_fraction = route_progress.median_fraction(eligible_fractions)
    trip_arrived = route_progress.trip_has_arrived(route_states, eligible_user_ids)

    return results, group_fraction, trip_arrived


async def get_live_route_progress(
    db: Session, redis: Redis, trip: Trip, route: Route
) -> Tuple[List[MemberRouteProgress], Optional[float], bool]:
    """Entry point for GET /trips/{trip_id}/route/progress: loads members
    and their live Redis state itself, then delegates to
    compute_route_progress(). app/intelligence/engine.py's per-tick call
    fetches this same live state anyway and calls compute_route_progress()
    directly to avoid the redundant Redis round trip."""
    now = datetime.now(timezone.utc)
    members = await run_in_threadpool(_load_active_members_sync, db, trip.group_id)
    user_ids = [m["user_id"] for m in members]
    live_locations = await live_state_service.get_live_locations(redis, trip.id, user_ids)
    online_status = await presence_service.get_online_status(redis, trip.id, user_ids)
    return await compute_route_progress(redis, trip.id, route, members, live_locations, online_status, now)
