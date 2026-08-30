"""
app/route/progress.py: route-state classification, median group progress,
trip-level arrival, and the ARRIVED confirmation debounce timer (fakeredis
— no live Redis required, same pattern as test_intelligence_detectors.py).
"""

from datetime import datetime, timedelta, timezone

from app.intelligence.thresholds import Thresholds
from app.route import progress as route_progress

TRIP_ID = "11111111-1111-1111-1111-111111111111"
NOW = datetime(2026, 8, 30, 12, 0, 0, tzinfo=timezone.utc)

THRESHOLDS = Thresholds(
    stop_speed_mps=0.8,
    stop_duration_seconds=120,
    stale_location_seconds=60,
    falling_behind_distance_meters=500.0,
    falling_behind_duration_seconds=120,
    group_separation_distance_meters=800.0,
    group_separation_duration_seconds=120,
    isolated_member_distance_meters=1000.0,
    isolated_member_duration_seconds=120,
    max_reasonable_speed_mps=45.0,
    speed_anomaly_duration_seconds=20,
    group_cohesion_distance_meters=300.0,
    min_usable_accuracy_meters=100.0,
    evaluation_interval_seconds=3.0,
    route_endpoint_tolerance_meters=200.0,
    off_route_threshold_meters=100.0,
    route_deviation_duration_seconds=60,
    arrival_threshold_meters=50.0,
    arrival_duration_seconds=30,
    route_progress_stale_seconds=60,
    baseline_route_speed_mps=11.0,
)


# ---- classify_route_state --------------------------------------------------


def test_on_route_when_close_and_far_from_destination():
    state = route_progress.classify_route_state(
        distance_from_route_meters=10.0, distance_remaining_meters=5000.0, confirmed_arrived=False, thresholds=THRESHOLDS
    )
    assert state == route_progress.ON_ROUTE


def test_off_route_when_beyond_threshold():
    state = route_progress.classify_route_state(
        distance_from_route_meters=250.0, distance_remaining_meters=5000.0, confirmed_arrived=False, thresholds=THRESHOLDS
    )
    assert state == route_progress.OFF_ROUTE


def test_near_destination_overrides_off_route_reading():
    """Close to the end of the route, distance-from-line noise shouldn't
    matter as much as proximity to the destination — NEAR_DESTINATION
    takes priority once within the derived multiple of ARRIVAL_THRESHOLD."""
    state = route_progress.classify_route_state(
        distance_from_route_meters=10.0, distance_remaining_meters=100.0, confirmed_arrived=False, thresholds=THRESHOLDS
    )
    assert state == route_progress.NEAR_DESTINATION


def test_confirmed_arrived_wins_regardless_of_instantaneous_distances():
    state = route_progress.classify_route_state(
        distance_from_route_meters=999.0, distance_remaining_meters=999.0, confirmed_arrived=True, thresholds=THRESHOLDS
    )
    assert state == route_progress.ARRIVED


# ---- compute_confirmed_arrival (Redis-backed debounce) --------------------


async def test_arrival_not_confirmed_on_first_tick(fake_redis):
    confirmed = await route_progress.compute_confirmed_arrival(fake_redis, TRIP_ID, "u1", 10.0, THRESHOLDS, NOW)
    assert confirmed is False


async def test_arrival_confirmed_after_sustained_proximity(fake_redis):
    await route_progress.compute_confirmed_arrival(fake_redis, TRIP_ID, "u1", 10.0, THRESHOLDS, NOW)
    later = NOW + timedelta(seconds=THRESHOLDS.arrival_duration_seconds + 1)
    confirmed = await route_progress.compute_confirmed_arrival(fake_redis, TRIP_ID, "u1", 10.0, THRESHOLDS, later)
    assert confirmed is True


async def test_moving_away_resets_the_arrival_timer(fake_redis):
    await route_progress.compute_confirmed_arrival(fake_redis, TRIP_ID, "u1", 10.0, THRESHOLDS, NOW)
    moved_away = NOW + timedelta(seconds=10)
    await route_progress.compute_confirmed_arrival(fake_redis, TRIP_ID, "u1", 500.0, THRESHOLDS, moved_away)

    back_within_old_window = moved_away + timedelta(seconds=THRESHOLDS.arrival_duration_seconds - 1)
    confirmed = await route_progress.compute_confirmed_arrival(
        fake_redis, TRIP_ID, "u1", 10.0, THRESHOLDS, back_within_old_window
    )
    assert confirmed is False  # timer restarted, didn't carry over the earlier progress


# ---- median_fraction --------------------------------------------------


def test_median_fraction_empty_is_none():
    assert route_progress.median_fraction([]) is None


def test_median_fraction_odd_count():
    assert route_progress.median_fraction([0.1, 0.9, 0.5]) == 0.5


def test_median_fraction_even_count_averages_middle_two():
    assert route_progress.median_fraction([0.2, 0.4, 0.6, 0.8]) == 0.5


def test_median_fraction_resists_a_single_outlier():
    """One member way out ahead must not drag the reported group progress
    with them the way a mean would."""
    values = [0.1, 0.12, 0.15, 0.98]
    median = route_progress.median_fraction(values)
    mean = sum(values) / len(values)
    assert median < mean


# ---- trip_has_arrived --------------------------------------------------


def test_trip_not_arrived_with_no_eligible_members():
    assert route_progress.trip_has_arrived({}, []) is False


def test_trip_arrived_when_every_eligible_member_confirmed():
    states = {"a": route_progress.ARRIVED, "b": route_progress.ARRIVED}
    assert route_progress.trip_has_arrived(states, ["a", "b"]) is True


def test_trip_not_arrived_while_one_member_still_en_route():
    states = {"a": route_progress.ARRIVED, "b": route_progress.NEAR_DESTINATION}
    assert route_progress.trip_has_arrived(states, ["a", "b"]) is False
