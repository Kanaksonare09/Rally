"""
Trip replay — GET /trips/{trip_id}/replay. Turns raw location_history into
a compact, evenly-sampled timeline a frontend can scrub through, instead
of shipping every raw GPS point (a long trip can easily have tens of
thousands of them per member).

Sampling strategy: pick a fixed set of global timestamps
`interval_seconds` apart, spanning the trip's actual GPS data range; for
each member at each timestamp, carry forward their most recent point at
or before that time (never interpolate a fake position between two real
readings — a member with no point yet at a given timestamp is simply
absent from that frame's `members` list, not synthesized). Movement state
per frame comes from Phase 7's persisted MOVING/STOPPED transition
history (the same source app/analytics/queries.py::
fetch_movement_intervals_by_user already gives member_analytics /
dashboard) — never guessed from raw speed a second, different way.
Route progress per frame is computed by matching that carried-forward
point against the route's stored geometry (Phase 9's own matcher,
app/route/matcher.py) — the same math live tracking uses, just run once
per historical point instead of continuously.

Events reuse app/analytics/timeline.py::build_timeline() wholesale — the
same chronological trip/route/intelligence/alert/SOS event list
GET /trips/{trip_id}/timeline already returns, so replay and timeline can
never disagree about what happened during a trip.
"""

import uuid
from datetime import datetime
from typing import Dict, List, Optional, Tuple

from sqlalchemy.orm import Session

from app.analytics import queries, timeline as timeline_module
from app.analytics.queries import LocationPoint, MovementInterval
from app.core.config import settings
from app.models.trip import Trip
from app.route import service as route_service
from app.route.matcher import RouteGeometry, build_route_geometry, match_point_to_route
from app.schemas.analytics import ReplayFrame, ReplayMemberState, TripReplay


def _clamp_interval(interval_seconds: Optional[int]) -> int:
    value = interval_seconds if interval_seconds is not None else settings.REPLAY_DEFAULT_INTERVAL_SECONDS
    return max(settings.REPLAY_MIN_INTERVAL_SECONDS, min(settings.REPLAY_MAX_INTERVAL_SECONDS, value))


def _state_at(intervals: List[MovementInterval], t: datetime, trip_end: datetime) -> Optional[str]:
    """Which MOVING/STOPPED interval (if any) covers timestamp `t` — an
    interval still open at trip end (no resolved_at) is treated as
    extending to `trip_end`, the same rule
    queries.compute_movement_durations() uses."""
    for state, started_at, ended_at in intervals:
        end = ended_at if ended_at is not None else trip_end
        if started_at <= t <= end:
            return state
    return None


def _advance_pointer(points: List[LocationPoint], pointer: int, t: datetime) -> int:
    """Advances `pointer` to the last index whose recorded_at <= t,
    without stepping past it — points are pre-sorted ascending, and the
    global timestamp sequence this is called with is also ascending, so
    each member's pointer only ever moves forward across a whole replay
    (O(n) total per member, not O(n*frames))."""
    next_pointer = pointer
    while next_pointer + 1 < len(points) and points[next_pointer + 1][3] <= t:
        next_pointer += 1
    return next_pointer


def build_replay(db: Session, trip: Trip, *, interval_seconds: Optional[int] = None) -> TripReplay:
    interval = _clamp_interval(interval_seconds)

    points_by_user = queries.fetch_location_points(db, trip.id)
    events = timeline_module.build_timeline(db, trip)

    if not points_by_user:
        return TripReplay(
            trip_id=trip.id,
            duration_seconds=queries.compute_trip_duration_seconds(trip),
            total_distance_meters=None,
            interval_seconds=interval,
            timeline=[],
            events=events,
        )

    leader_id = queries.get_group_leader_id(db, trip.group_id)
    distances_by_user = queries.compute_distances_by_user(
        points_by_user, max_speed_mps=settings.MAX_ANALYTICS_SPEED_MPS, max_accuracy_meters=settings.MIN_USABLE_ACCURACY_METERS
    )
    total_distance = queries.pick_representative_value(distances_by_user, leader_id)

    movement_by_user = queries.fetch_movement_intervals_by_user(db, trip.id)

    route = route_service.get_route_by_trip(db, trip.id)
    geometry: Optional[RouteGeometry] = None
    if route is not None and route.coordinates:
        try:
            geometry = build_route_geometry(route.coordinates)
        except ValueError:
            geometry = None

    start = min(points[0][3] for points in points_by_user.values())
    end = max(points[-1][3] for points in points_by_user.values())
    trip_end = trip.ended_at or end

    span_seconds = max(0.0, (end - start).total_seconds())
    frame_count = int(span_seconds // interval) + 1
    if frame_count > settings.REPLAY_MAX_FRAMES:
        # Silently coarsen rather than truncate the trip — every replay
        # request for a given trip gets the SAME frame count ceiling
        # applied the same deterministic way, never an arbitrarily cut-off
        # ending.
        interval = max(interval, int(span_seconds / settings.REPLAY_MAX_FRAMES) + 1)
        frame_count = int(span_seconds // interval) + 1

    pointers: Dict[str, int] = {uid: 0 for uid in points_by_user}
    frames: List[ReplayFrame] = []

    for i in range(frame_count):
        t = start if span_seconds == 0 else _frame_timestamp(start, interval, i, end)
        members: List[ReplayMemberState] = []

        for user_id, points in points_by_user.items():
            if points[0][3] > t:
                continue  # this member hasn't started sending GPS yet as of this frame
            pointers[user_id] = _advance_pointer(points, pointers[user_id], t)
            lat, lon, _accuracy, recorded_at = points[pointers[user_id]]

            movement_state = _state_at(movement_by_user.get(user_id, []), recorded_at, trip_end)

            route_progress = None
            if geometry is not None:
                try:
                    match = match_point_to_route(geometry, lat, lon)
                    route_progress = round(match.route_fraction, 3)
                except ValueError:
                    route_progress = None

            members.append(
                ReplayMemberState(
                    user_id=uuid.UUID(user_id), latitude=lat, longitude=lon,
                    movement_state=movement_state, route_progress=route_progress,
                )
            )

        if members:
            frames.append(ReplayFrame(timestamp=t, members=members))

    return TripReplay(
        trip_id=trip.id,
        duration_seconds=queries.compute_trip_duration_seconds(trip),
        total_distance_meters=round(total_distance) if total_distance is not None else None,
        interval_seconds=interval,
        timeline=frames,
        events=events,
    )


def _frame_timestamp(start: datetime, interval_seconds: int, index: int, end: datetime) -> datetime:
    from datetime import timedelta

    candidate = start + timedelta(seconds=interval_seconds * index)
    return min(candidate, end)
