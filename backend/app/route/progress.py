"""
Turning a raw RouteMatch (app/route/matcher.py) into the user-facing route
state (ON_ROUTE / OFF_ROUTE / NEAR_DESTINATION / ARRIVED), plus the group-
level aggregation (median progress) the spec calls for.

ARRIVED is the one state that needs debounce: a member sitting right at
ARRIVAL_THRESHOLD_METERS from the destination must not flap between
NEAR_DESTINATION and ARRIVED on every noisy GPS point, so confirmation
requires the proximity to hold for ARRIVAL_DURATION_SECONDS — the same
persistence-timer shape app.intelligence.detectors uses, kept here as its
own small helper rather than imported from there, since "arrived" is
deliberately NOT a persisted IntelligenceEventType (see ROUTE_DEVIATION,
the one route-related type that *is* persisted, in
app/intelligence/detectors.py).

OFF_ROUTE and NEAR_DESTINATION, by contrast, are plain instantaneous
labels — safe to flicker tick to tick, since they're descriptive fields on
a progress snapshot, not events. The ROUTE_DEVIATION *event* has its own,
separate persistence gate (ROUTE_DEVIATION_DURATION_SECONDS) in
app/intelligence/detectors.py::detect_route_deviation.
"""

import json
from datetime import datetime
from typing import Dict, Optional, Sequence

from redis.asyncio import Redis

from app.core.redis_keys import route_condition_key
from app.intelligence.thresholds import Thresholds

# NEAR_DESTINATION has no independent config constant in this phase's
# spec — it's derived from ARRIVAL_THRESHOLD_METERS as a fixed multiple,
# not separately tunable.
NEAR_DESTINATION_MULTIPLIER = 3.0

ON_ROUTE = "ON_ROUTE"
OFF_ROUTE = "OFF_ROUTE"
NEAR_DESTINATION = "NEAR_DESTINATION"
ARRIVED = "ARRIVED"


def classify_route_state(
    *, distance_from_route_meters: float, distance_remaining_meters: float, confirmed_arrived: bool, thresholds: Thresholds
) -> str:
    """Pure, no I/O — `confirmed_arrived` is computed separately (see
    compute_confirmed_arrival) since only that part needs persistence."""
    if confirmed_arrived:
        return ARRIVED
    if distance_remaining_meters <= thresholds.arrival_threshold_meters * NEAR_DESTINATION_MULTIPLIER:
        return NEAR_DESTINATION
    if distance_from_route_meters > thresholds.off_route_threshold_meters:
        return OFF_ROUTE
    return ON_ROUTE


async def _arrival_condition_elapsed_seconds(
    redis: Redis, trip_id, user_id, currently_within: bool, now: datetime
) -> float:
    key = route_condition_key(trip_id, "arrival", user_id)
    if not currently_within:
        await redis.delete(key)
        return 0.0

    raw = await redis.get(key)
    if raw is None:
        await redis.set(key, json.dumps({"since": now.isoformat()}), ex=3600)
        return 0.0

    since = datetime.fromisoformat(json.loads(raw)["since"])
    return (now - since).total_seconds()


async def compute_confirmed_arrival(
    redis: Redis, trip_id, user_id, distance_remaining_meters: float, thresholds: Thresholds, now: datetime
) -> bool:
    currently_within = distance_remaining_meters <= thresholds.arrival_threshold_meters
    elapsed = await _arrival_condition_elapsed_seconds(redis, trip_id, user_id, currently_within, now)
    return currently_within and elapsed >= thresholds.arrival_duration_seconds


def median_fraction(fractions: Sequence[float]) -> Optional[float]:
    """Median, not mean, for the spec's "group progress via median
    aggregation" — one member way out ahead or badly behind shouldn't
    single-handedly drag the reported group progress with them the way an
    average would."""
    if not fractions:
        return None
    ordered = sorted(fractions)
    n = len(ordered)
    mid = n // 2
    if n % 2 == 1:
        return ordered[mid]
    return (ordered[mid - 1] + ordered[mid]) / 2.0


def trip_has_arrived(route_states_by_user: Dict[str, str], eligible_user_ids: Sequence[str]) -> bool:
    """True only once every member who's actually being tracked right now
    (i.e. excluding OFFLINE/STALE members — `eligible_user_ids` is the
    caller's already-filtered list) has a confirmed ARRIVED state. An
    empty eligible list is never "arrived" — there's no one to confirm it."""
    if not eligible_user_ids:
        return False
    return all(route_states_by_user.get(uid) == ARRIVED for uid in eligible_user_ids)
