"""
Read-only aggregation primitives for the analytics layer. Nothing in this
module (or any other app/analytics/ module) ever writes to
location_history, intelligence_events, alerts, or sos_events — analytics
only reads and summarizes what those tables already recorded.

Design note on scale (see the backend README's Analytics/Performance
section for the full reasoning): distance-traveled is computed by pulling
only the four columns actually needed (user_id, latitude, longitude,
accuracy, recorded_at) — never the full row/geometry — ordered
server-side, then summed with the same pure-Python Haversine approach
already used for exactly this kind of calculation in
app/intelligence/distance.py and app/route/matcher.py. That keeps this
module consistent with the rest of the codebase's established pattern and
fully unit-testable without a live PostGIS connection. Everything else
(alerts, SOS, intelligence events) reuses the existing list_*() functions
from app/alerts/service.py, app/sos/service.py, and
app/intelligence/events.py rather than duplicating new queries — at the
row counts one trip realistically produces, aggregating those lists in
Python is simpler and just as fast as a bespoke GROUP BY, and it means
this module never drifts out of sync with what those services consider
"an alert"/"active."
"""

import uuid
from datetime import datetime, timezone
from typing import Dict, List, Optional, Sequence, Tuple

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.intelligence import events as intelligence_events
from app.intelligence.distance import haversine_distance_meters
from app.models.enums import IntelligenceEventType, MemberStatus, TripStatus
from app.models.group_member import GroupMember
from app.models.location_history import LocationHistory
from app.models.profile import Profile
from app.models.trip import Trip


def compute_trip_duration_seconds(trip: Trip) -> Optional[int]:
    """None for a trip that never started (CREATED, or CANCELLED before
    ever starting) — "how long was the trip" has no answer if it never
    ran, and returning 0 would misleadingly suggest it did. Never
    negative: a COMPLETED trip whose ended_at somehow precedes started_at
    (should not happen given trip_service's own state machine, but this
    function does not trust that from the outside) is clamped to 0."""
    if trip.started_at is None:
        return None

    if trip.status == TripStatus.ACTIVE:
        end = datetime.now(timezone.utc)
    elif trip.ended_at is not None:
        end = trip.ended_at
    else:
        # Started but neither ACTIVE nor ever given an ended_at (e.g. a
        # CANCELLED trip that had somehow already started) — nothing
        # reliable to measure against.
        return None

    return max(0, int((end - trip.started_at).total_seconds()))

# lat, lon, accuracy, recorded_at
LocationPoint = Tuple[float, float, Optional[float], datetime]


def list_active_group_members(db: Session, group_id: uuid.UUID) -> List[dict]:
    """The group's current active membership — the same scope every other
    "who's in this group" query in this codebase uses (e.g.
    app/intelligence/engine.py, app/route/service.py). A member who has
    since left or been removed won't appear here even if they
    participated in a past trip — a documented, deliberate scope choice,
    not an oversight; see the README."""
    rows = db.execute(
        select(GroupMember, Profile)
        .join(Profile, GroupMember.user_id == Profile.id)
        .where(GroupMember.group_id == group_id, GroupMember.status == MemberStatus.ACTIVE)
    ).all()
    return [
        {
            "user_id": member.user_id,
            "name": profile.full_name,
            "role": member.role.value,
            "joined_at": member.joined_at,
        }
        for member, profile in rows
    ]


def get_group_leader_id(db: Session, group_id: uuid.UUID) -> Optional[uuid.UUID]:
    from app.models.enums import MemberRole

    member = db.scalars(
        select(GroupMember).where(
            GroupMember.group_id == group_id,
            GroupMember.role == MemberRole.LEADER,
            GroupMember.status == MemberStatus.ACTIVE,
        )
    ).first()
    return member.user_id if member else None


def fetch_location_points(db: Session, trip_id: uuid.UUID) -> Dict[str, List[LocationPoint]]:
    """Every GPS point for the trip, grouped by user and already sorted
    (recorded_at ascending within each user) — one indexed query
    (ix_location_history_trip_recorded), only the columns distance/active-
    duration/route-matching actually need. A user with zero points on this
    trip simply has no key in the returned dict — callers use that
    absence, not an empty list, to distinguish "no GPS data at all" from
    "had GPS data but nothing usable in it"."""
    rows = db.execute(
        select(
            LocationHistory.user_id,
            LocationHistory.latitude,
            LocationHistory.longitude,
            LocationHistory.accuracy,
            LocationHistory.recorded_at,
        )
        .where(LocationHistory.trip_id == trip_id)
        .order_by(LocationHistory.user_id, LocationHistory.recorded_at)
    ).all()

    points_by_user: Dict[str, List[LocationPoint]] = {}
    for user_id, lat, lon, accuracy, recorded_at in rows:
        points_by_user.setdefault(str(user_id), []).append((lat, lon, accuracy, recorded_at))
    return points_by_user


def compute_member_distance_meters(
    points: Sequence[LocationPoint], *, max_speed_mps: float, max_accuracy_meters: Optional[float]
) -> Optional[float]:
    """Sums consecutive-point Haversine distance, skipping GPS noise
    rather than blindly trusting every row:

      - a point whose reported accuracy is worse than
        `max_accuracy_meters` is dropped entirely before segments are
        even formed (so the *next* good point is compared against the
        last *good* point, not the noisy one) — GPS_DISTANCE_FILTERING;
      - a segment implying a speed above `max_speed_mps` is treated as an
        impossible jump: it's skipped and the anchor point is left where
        it was, so a single corrupted fix can't also poison the segment
        that follows it;
      - a segment with zero or negative elapsed time (out-of-order or
        duplicate timestamps) is skipped the same way.

    Returns None only when `points` itself is empty (no GPS data at all
    for this member on this trip) — a single point, or a run of points
    that never produces a single valid segment, correctly returns 0.0
    (there was data; no measurable distance could be attributed), never
    None. This is the zero-vs-null line the rest of the analytics layer
    depends on.
    """
    if not points:
        return None

    usable = [p for p in points if p[2] is None or max_accuracy_meters is None or p[2] <= max_accuracy_meters]
    if not usable:
        return 0.0

    total_meters = 0.0
    anchor = usable[0]
    for point in usable[1:]:
        lat1, lon1, _, t1 = anchor
        lat2, lon2, _, t2 = point
        elapsed_seconds = (t2 - t1).total_seconds()
        if elapsed_seconds <= 0:
            continue

        segment_meters = haversine_distance_meters(lat1, lon1, lat2, lon2)
        implied_speed_mps = segment_meters / elapsed_seconds
        if implied_speed_mps > max_speed_mps:
            continue

        total_meters += segment_meters
        anchor = point

    return total_meters


def compute_distances_by_user(
    points_by_user: Dict[str, List[LocationPoint]], *, max_speed_mps: float, max_accuracy_meters: Optional[float]
) -> Dict[str, float]:
    """compute_member_distance_meters() applied across every member, with
    the None ("no GPS at all") members dropped rather than kept as None
    values — the shape pick_representative_value() and any "which members
    have a usable distance" caller wants. Used by both trip- and route-
    level analytics so the two never compute this two different ways."""
    result: Dict[str, float] = {}
    for user_id, points in points_by_user.items():
        distance = compute_member_distance_meters(points, max_speed_mps=max_speed_mps, max_accuracy_meters=max_accuracy_meters)
        if distance is not None:
            result[user_id] = distance
    return result


def compute_active_duration_seconds(points: Sequence[LocationPoint]) -> Optional[float]:
    """Time between a member's first and last recorded GPS point on the
    trip — None with fewer than 2 points (nothing to span)."""
    if len(points) < 2:
        return None
    first_recorded_at = points[0][3]
    last_recorded_at = points[-1][3]
    return max(0.0, (last_recorded_at - first_recorded_at).total_seconds())


def pick_representative_value(values_by_user: Dict[str, float], leader_id: Optional[uuid.UUID]) -> Optional[float]:
    """The single deterministic "group" figure for a metric multiple
    members each have their own value for (distance traveled, route
    fraction) — summing every member's value would double/triple-count
    the same shared journey.

    Prefers the group leader's own value when it's available (the most
    intuitive "the group's progress" proxy — see the README). Falls back
    to the median across whichever members do have a value, which is
    deterministic and resistant to one outlier the way a mean isn't.
    Returns None only when no member has a usable value at all."""
    if not values_by_user:
        return None

    leader_key = str(leader_id) if leader_id is not None else None
    if leader_key is not None and leader_key in values_by_user:
        return values_by_user[leader_key]

    ordered = sorted(values_by_user.values())
    n = len(ordered)
    mid = n // 2
    if n % 2 == 1:
        return ordered[mid]
    return (ordered[mid - 1] + ordered[mid]) / 2.0


# ---- Movement duration (from Phase 7's persisted MOVING/STOPPED transitions) --


MovementInterval = Tuple[str, datetime, Optional[datetime]]  # (state, started_at, ended_at)


def compute_movement_durations(
    intervals: Sequence[MovementInterval], *, trip_end: datetime
) -> Tuple[bool, Optional[float], Optional[float]]:
    """`intervals` is one member's MOVING/STOPPED intelligence_events rows
    (see app/intelligence/engine.py::_apply_movement_transitions, which
    persists every transition as a real row — this is genuine historical
    state, not something this function invents). Each interval spans
    [started_at, ended_at or trip_end] — an interval still open at trip
    end (the worker only evaluates ACTIVE trips, so the final state never
    gets an explicit resolved_at) is closed at `trip_end` instead.

    Returns (movement_duration_available, moving_seconds, stopped_seconds).
    `movement_duration_available` is False — with both durations None,
    never 0 — only when this member has no such interval recorded at all
    (e.g. the intelligence worker never evaluated this trip): STALE/
    OFFLINE time is never included in either total and is not reported as
    its own metric, since no historical record of it exists (see the
    README's Movement analytics section)."""
    if not intervals:
        return False, None, None

    moving_seconds = 0.0
    stopped_seconds = 0.0
    for state, started_at, ended_at in intervals:
        end = ended_at if ended_at is not None else trip_end
        duration = max(0.0, (end - started_at).total_seconds())
        if state == "MOVING":
            moving_seconds += duration
        elif state == "STOPPED":
            stopped_seconds += duration

    return True, moving_seconds, stopped_seconds


def fetch_movement_intervals_by_user(db: Session, trip_id: uuid.UUID) -> Dict[str, List[MovementInterval]]:
    """Every persisted MOVING/STOPPED transition for the trip (see
    app/intelligence/engine.py::_apply_movement_transitions), grouped by
    user and sorted chronologically — reused by both member_analytics.py
    (duration totals) and dashboard.py (a completed trip's last-known
    movement_state per member), via the same two list_events() calls
    rather than two different queries that could disagree."""
    moving = intelligence_events.list_events(db, trip_id, event_type=IntelligenceEventType.MOVING, limit=5000)
    stopped = intelligence_events.list_events(db, trip_id, event_type=IntelligenceEventType.STOPPED, limit=5000)

    by_user: Dict[str, List[MovementInterval]] = {}
    for event in moving + stopped:
        if event.user_id is None:
            continue
        state = "MOVING" if event.event_type == IntelligenceEventType.MOVING else "STOPPED"
        by_user.setdefault(str(event.user_id), []).append((state, event.detected_at, event.resolved_at))

    for intervals in by_user.values():
        intervals.sort(key=lambda item: item[1])
    return by_user
