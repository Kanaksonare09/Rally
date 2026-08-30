"""
Route completion and deviation statistics — reuses Phase 9's own geometry/
matching code (app/route/matcher.py) rather than re-deriving progress a
second way, and Phase 7/8's persisted ROUTE_DEVIATION intelligence_events
for deviation history. Nothing here needs Redis: a completed trip's route
progress is recomputed from each member's *last* location_history point
against the route's persisted geometry — the exact same matching Phase 9
does live, just run once against historical data instead of a live feed.
"""

import uuid
from typing import Dict, List, Optional, Tuple

from sqlalchemy.orm import Session

from app.analytics import queries
from app.analytics.queries import LocationPoint
from app.intelligence import events as intelligence_events
from app.intelligence.thresholds import current_thresholds
from app.models.enums import IntelligenceEventType
from app.models.route import Route
from app.models.trip import Trip
from app.route import service as route_service
from app.route.matcher import RouteMatch, build_route_geometry, match_point_to_route
from app.schemas.analytics import RouteAnalytics


def match_last_point(route: Route, points: List[LocationPoint]) -> Optional[RouteMatch]:
    """The route match for one member's most recent GPS point on this
    trip — used for a historical (post-trip) route_state label, since
    Redis's live match state doesn't survive a trip ending. None when the
    route has no usable geometry or the member has no points at all."""
    if not route.coordinates or not points:
        return None
    try:
        geometry = build_route_geometry(route.coordinates)
    except ValueError:
        return None
    last_lat, last_lon, _, _ = points[-1]
    try:
        return match_point_to_route(geometry, last_lat, last_lon)
    except ValueError:
        return None


def compute_route_completion(
    route: Route, points_by_user: Dict[str, List[LocationPoint]], leader_id: Optional[uuid.UUID]
) -> Tuple[Optional[float], Optional[float], Optional[bool]]:
    """The representative route_fraction/distance-remaining/arrived triple
    for a trip, derived from each member's *last* GPS point matched
    against the route — the same "leader, else median" representative
    logic app/analytics/queries.py::pick_representative_value uses for
    distance, applied here to route_fraction so the two headline metrics
    ("how far did the group go" / "how much of the route is done") are
    computed consistently.

    Returns (completion_percent, distance_remaining_meters, arrived) —
    all None when there's no usable final point for any member.
    """
    if not route.coordinates or not points_by_user:
        return None, None, None

    try:
        geometry = build_route_geometry(route.coordinates)
    except ValueError:
        return None, None, None

    fractions_by_user: Dict[str, float] = {}
    remaining_by_user: Dict[str, float] = {}
    for user_id, points in points_by_user.items():
        if not points:
            continue
        last_lat, last_lon, _, _ = points[-1]
        try:
            match = match_point_to_route(geometry, last_lat, last_lon)
        except ValueError:
            continue
        fractions_by_user[user_id] = match.route_fraction
        remaining_by_user[user_id] = match.distance_remaining_meters

    if not fractions_by_user:
        return None, None, None

    representative_fraction = queries.pick_representative_value(fractions_by_user, leader_id)
    representative_remaining = queries.pick_representative_value(remaining_by_user, leader_id)
    if representative_fraction is None:
        return None, None, None

    thresholds = current_thresholds()
    arrived = (
        representative_remaining is not None and representative_remaining <= thresholds.arrival_threshold_meters
    )
    return round(representative_fraction * 100, 1), representative_remaining, arrived


def build_route_analytics(
    db: Session,
    trip: Trip,
    *,
    points_by_user: Optional[Dict[str, List[LocationPoint]]] = None,
    leader_id: Optional[uuid.UUID] = None,
) -> RouteAnalytics:
    route = route_service.get_route_by_trip(db, trip.id)
    if route is None:
        return RouteAnalytics(
            route_available=False, route_deviations=0, resolved_deviations=0, active_deviations=0
        )

    if points_by_user is None:
        points_by_user = queries.fetch_location_points(db, trip.id)
    if leader_id is None:
        leader_id = queries.get_group_leader_id(db, trip.group_id)

    completion_percent, _distance_remaining, arrived = compute_route_completion(route, points_by_user, leader_id)
    distances_by_user = queries.compute_distances_by_user(
        points_by_user, max_speed_mps=_max_analytics_speed(), max_accuracy_meters=_max_accuracy()
    )
    traveled_distance = queries.pick_representative_value(distances_by_user, leader_id)

    deviation_events = intelligence_events.list_events(
        db, trip.id, event_type=IntelligenceEventType.ROUTE_DEVIATION, limit=5000
    )
    total = len(deviation_events)
    resolved = sum(1 for e in deviation_events if e.resolved_at is not None)
    active = total - resolved

    observed_distances = [
        e.event_metadata.get("distance_from_route_meters")
        for e in deviation_events
        if isinstance(e.event_metadata, dict) and isinstance(e.event_metadata.get("distance_from_route_meters"), (int, float))
    ]
    average_deviation = round(sum(observed_distances) / len(observed_distances), 1) if observed_distances else None
    maximum_deviation = round(max(observed_distances), 1) if observed_distances else None

    return RouteAnalytics(
        route_available=True,
        planned_distance_meters=round(route.distance_meters),
        traveled_distance_meters=round(traveled_distance) if traveled_distance is not None else None,
        completion_percent=completion_percent,
        route_deviations=total,
        resolved_deviations=resolved,
        active_deviations=active,
        average_distance_from_route_meters=average_deviation,
        maximum_distance_from_route_meters=maximum_deviation,
        arrived=arrived,
    )


def _max_analytics_speed() -> float:
    from app.core.config import settings

    return settings.MAX_ANALYTICS_SPEED_MPS


def _max_accuracy() -> float:
    from app.core.config import settings

    return settings.MIN_USABLE_ACCURACY_METERS
