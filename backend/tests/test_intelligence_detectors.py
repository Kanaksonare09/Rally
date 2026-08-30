"""
Detector persistence-gating tests, against fakeredis (no real Redis
required — see tests/conftest.py's fake_redis fixture). Each detector must
NOT fire on a single tick and MUST fire once the condition has held for
its configured duration.
"""

import uuid
from datetime import datetime, timedelta, timezone

import pytest

from app.intelligence import detectors
from app.intelligence.group_analysis import MemberGroupAnalysis, GroupAnalysisResult
from app.intelligence.thresholds import Thresholds

TRIP_ID = uuid.uuid4()
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


def make_group(members: dict, eligible=None, clusters=None, cohesive=True) -> GroupAnalysisResult:
    return GroupAnalysisResult(
        center=(0.0, 0.0),
        eligible_member_ids=eligible if eligible is not None else list(members.keys()),
        members=members,
        max_pairwise_distance_meters=0.0,
        is_cohesive=cohesive,
        clusters=clusters if clusters is not None else [list(members.keys())],
    )


async def tick(fn, *args, **kwargs):
    return await fn(*args, **kwargs)


# ---- falling behind ---------------------------------------------------


async def test_falling_behind_within_threshold_not_flagged(fake_redis):
    group = make_group({"u1": MemberGroupAnalysis("u1", distance_from_center_meters=200, is_isolated=False, nearest_other_member_id=None, nearest_other_member_distance_meters=None)})
    results = await detectors.detect_falling_behind(fake_redis, TRIP_ID, group, THRESHOLDS, NOW)
    assert results[0].detected is False


async def test_falling_behind_beyond_threshold_not_immediately_flagged(fake_redis):
    """Single tick beyond threshold — must not fire yet (persistence gate)."""
    group = make_group({"u1": MemberGroupAnalysis("u1", distance_from_center_meters=700, is_isolated=False, nearest_other_member_id=None, nearest_other_member_distance_meters=None)})
    results = await detectors.detect_falling_behind(fake_redis, TRIP_ID, group, THRESHOLDS, NOW)
    assert results[0].detected is False


async def test_falling_behind_eventually_flagged_after_persistence(fake_redis):
    group = make_group({"u1": MemberGroupAnalysis("u1", distance_from_center_meters=700, is_isolated=False, nearest_other_member_id=None, nearest_other_member_distance_meters=None)})

    # First tick starts the timer.
    await detectors.detect_falling_behind(fake_redis, TRIP_ID, group, THRESHOLDS, NOW)
    # Second tick, past the duration threshold.
    later = NOW + timedelta(seconds=THRESHOLDS.falling_behind_duration_seconds + 1)
    results = await detectors.detect_falling_behind(fake_redis, TRIP_ID, group, THRESHOLDS, later)

    assert results[0].detected is True
    assert results[0].metadata["distance_meters"] == 700
    assert results[0].metadata["threshold_meters"] == THRESHOLDS.falling_behind_distance_meters


async def test_falling_behind_resets_when_member_returns(fake_redis):
    far = make_group({"u1": MemberGroupAnalysis("u1", 700, False, None, None)})
    close = make_group({"u1": MemberGroupAnalysis("u1", 100, False, None, None)})

    await detectors.detect_falling_behind(fake_redis, TRIP_ID, far, THRESHOLDS, NOW)
    # Comes back before the duration elapses.
    mid = NOW + timedelta(seconds=10)
    await detectors.detect_falling_behind(fake_redis, TRIP_ID, close, THRESHOLDS, mid)

    # Goes far again — timer must have reset, not resumed.
    later = mid + timedelta(seconds=THRESHOLDS.falling_behind_duration_seconds - 5)
    results = await detectors.detect_falling_behind(fake_redis, TRIP_ID, far, THRESHOLDS, later)
    assert results[0].detected is False


# ---- isolated member ----------------------------------------------------


async def test_isolated_member_eventually_flagged(fake_redis):
    group = make_group({"a": MemberGroupAnalysis("a", 0, True, "b", 1500)})
    await detectors.detect_isolated_member(fake_redis, TRIP_ID, group, THRESHOLDS, NOW)
    later = NOW + timedelta(seconds=THRESHOLDS.isolated_member_duration_seconds + 1)
    results = await detectors.detect_isolated_member(fake_redis, TRIP_ID, group, THRESHOLDS, later)
    assert results[0].detected is True
    assert results[0].related_user_id == "b"


async def test_not_isolated_never_flagged(fake_redis):
    group = make_group({"a": MemberGroupAnalysis("a", 0, False, "b", 100)})
    later = NOW + timedelta(seconds=1000)
    await detectors.detect_isolated_member(fake_redis, TRIP_ID, group, THRESHOLDS, NOW)
    results = await detectors.detect_isolated_member(fake_redis, TRIP_ID, group, THRESHOLDS, later)
    assert results[0].detected is False


# ---- group separation ----------------------------------------------------


async def test_group_separation_requires_persistence(fake_redis):
    group = make_group({"a": MemberGroupAnalysis("a", 0, False, None, None), "b": MemberGroupAnalysis("b", 0, False, None, None)}, clusters=[["a"], ["b"]])
    result = await detectors.detect_group_separation(fake_redis, TRIP_ID, group, THRESHOLDS, NOW)
    assert result.detected is False  # first tick, not yet persisted


async def test_group_separation_detected_after_persistence(fake_redis):
    group = make_group({"a": MemberGroupAnalysis("a", 0, False, None, None), "b": MemberGroupAnalysis("b", 0, False, None, None)}, clusters=[["a"], ["b"]])
    await detectors.detect_group_separation(fake_redis, TRIP_ID, group, THRESHOLDS, NOW)
    later = NOW + timedelta(seconds=THRESHOLDS.group_separation_duration_seconds + 1)
    result = await detectors.detect_group_separation(fake_redis, TRIP_ID, group, THRESHOLDS, later)
    assert result.detected is True
    assert result.metadata["cluster_sizes"] == [1, 1]


async def test_single_cluster_never_flags_separation(fake_redis):
    group = make_group({"a": MemberGroupAnalysis("a", 0, False, None, None)}, clusters=[["a"]])
    result = await detectors.detect_group_separation(fake_redis, TRIP_ID, group, THRESHOLDS, NOW)
    assert result.detected is False


# ---- speed anomaly ----------------------------------------------------


async def test_normal_speed_accepted(fake_redis):
    results = await detectors.detect_speed_anomaly(fake_redis, TRIP_ID, {"u1": 15.0}, {"u1": 5.0}, THRESHOLDS, NOW)
    assert results[0].detected is False


async def test_one_noisy_high_speed_reading_does_not_trigger(fake_redis):
    results = await detectors.detect_speed_anomaly(fake_redis, TRIP_ID, {"u1": 60.0}, {"u1": 5.0}, THRESHOLDS, NOW)
    assert results[0].detected is False  # first tick only


async def test_persistent_abnormal_speed_triggers(fake_redis):
    await detectors.detect_speed_anomaly(fake_redis, TRIP_ID, {"u1": 60.0}, {"u1": 5.0}, THRESHOLDS, NOW)
    later = NOW + timedelta(seconds=THRESHOLDS.speed_anomaly_duration_seconds + 1)
    results = await detectors.detect_speed_anomaly(fake_redis, TRIP_ID, {"u1": 60.0}, {"u1": 5.0}, THRESHOLDS, later)
    assert results[0].detected is True
    assert results[0].metadata["observed_speed_mps"] == 60.0


async def test_excessive_speed_with_bad_accuracy_is_ignored(fake_redis):
    """Speed reading paired with poor GPS accuracy shouldn't be trusted."""
    await detectors.detect_speed_anomaly(fake_redis, TRIP_ID, {"u1": 60.0}, {"u1": 500.0}, THRESHOLDS, NOW)
    later = NOW + timedelta(seconds=THRESHOLDS.speed_anomaly_duration_seconds + 1)
    results = await detectors.detect_speed_anomaly(fake_redis, TRIP_ID, {"u1": 60.0}, {"u1": 500.0}, THRESHOLDS, later)
    assert results[0].detected is False


# ---- unexpected stop ----------------------------------------------------


async def test_unexpected_stop_requires_others_still_moving(fake_redis):
    """Everyone stopped together (e.g. a lunch break) must never trigger —
    only a stop while the rest of the group keeps moving."""
    states = {"a": "STOPPED", "b": "STOPPED"}
    later = NOW + timedelta(seconds=THRESHOLDS.stop_duration_seconds + 1)
    await detectors.detect_unexpected_stop(fake_redis, TRIP_ID, states, THRESHOLDS, NOW)
    results = await detectors.detect_unexpected_stop(fake_redis, TRIP_ID, states, THRESHOLDS, later)
    assert results[0].detected is False


async def test_unexpected_stop_triggers_when_group_keeps_moving(fake_redis):
    states = {"a": "STOPPED", "b": "MOVING"}
    await detectors.detect_unexpected_stop(fake_redis, TRIP_ID, states, THRESHOLDS, NOW)
    later = NOW + timedelta(seconds=THRESHOLDS.stop_duration_seconds + 1)
    results = await detectors.detect_unexpected_stop(fake_redis, TRIP_ID, states, THRESHOLDS, later)
    assert results[0].user_id == "a"
    assert results[0].detected is True


# ---- moving together (positive state) ------------------------------------


async def test_moving_together_detected_when_cohesive_and_moving(fake_redis):
    group = make_group(
        {"a": MemberGroupAnalysis("a", 0, False, "b", 50), "b": MemberGroupAnalysis("b", 0, False, "a", 50)},
        clusters=[["a", "b"]], cohesive=True,
    )
    states = {"a": "MOVING", "b": "MOVING"}
    result = await detectors.detect_moving_together(fake_redis, TRIP_ID, group, states, THRESHOLDS, NOW)
    assert result.detected is True


async def test_moving_together_not_detected_when_separated(fake_redis):
    group = make_group(
        {"a": MemberGroupAnalysis("a", 0, False, None, None), "b": MemberGroupAnalysis("b", 0, False, None, None)},
        clusters=[["a"], ["b"]], cohesive=False,
    )
    states = {"a": "MOVING", "b": "MOVING"}
    result = await detectors.detect_moving_together(fake_redis, TRIP_ID, group, states, THRESHOLDS, NOW)
    assert result.detected is False


async def test_moving_together_not_detected_when_nobody_moving(fake_redis):
    group = make_group(
        {"a": MemberGroupAnalysis("a", 0, False, "b", 50), "b": MemberGroupAnalysis("b", 0, False, "a", 50)},
        clusters=[["a", "b"]], cohesive=True,
    )
    states = {"a": "STOPPED", "b": "STOPPED"}
    result = await detectors.detect_moving_together(fake_redis, TRIP_ID, group, states, THRESHOLDS, NOW)
    assert result.detected is False


async def test_moving_together_requires_at_least_two_members(fake_redis):
    group = make_group({"a": MemberGroupAnalysis("a", 0, False, None, None)}, clusters=[["a"]], cohesive=True)
    states = {"a": "MOVING"}
    result = await detectors.detect_moving_together(fake_redis, TRIP_ID, group, states, THRESHOLDS, NOW)
    assert result.detected is False


# ---- route deviation (Phase 9) --------------------------------------------


async def test_on_route_never_flagged(fake_redis):
    results = await detectors.detect_route_deviation(fake_redis, TRIP_ID, {"a": 20.0}, THRESHOLDS, NOW)
    assert results[0].detected is False
    assert results[0].metadata == {}


async def test_one_noisy_off_route_reading_does_not_trigger(fake_redis):
    results = await detectors.detect_route_deviation(fake_redis, TRIP_ID, {"a": 250.0}, THRESHOLDS, NOW)
    assert results[0].detected is False  # first tick only


async def test_persistent_off_route_eventually_triggers(fake_redis):
    await detectors.detect_route_deviation(fake_redis, TRIP_ID, {"a": 250.0}, THRESHOLDS, NOW)
    later = NOW + timedelta(seconds=THRESHOLDS.route_deviation_duration_seconds + 1)
    results = await detectors.detect_route_deviation(fake_redis, TRIP_ID, {"a": 250.0}, THRESHOLDS, later)
    assert results[0].detected is True
    assert results[0].metadata["distance_from_route_meters"] == 250.0
    assert results[0].metadata["threshold_meters"] == THRESHOLDS.off_route_threshold_meters


async def test_returning_to_route_resets_the_timer(fake_redis):
    await detectors.detect_route_deviation(fake_redis, TRIP_ID, {"a": 250.0}, THRESHOLDS, NOW)
    back_on_route = NOW + timedelta(seconds=THRESHOLDS.route_deviation_duration_seconds + 1)
    await detectors.detect_route_deviation(fake_redis, TRIP_ID, {"a": 20.0}, THRESHOLDS, back_on_route)

    resumed_deviation = back_on_route + timedelta(seconds=1)
    results = await detectors.detect_route_deviation(fake_redis, TRIP_ID, {"a": 250.0}, THRESHOLDS, resumed_deviation)
    assert results[0].detected is False  # timer restarted, not carried over


async def test_member_with_no_usable_match_is_not_flagged(fake_redis):
    """A member absent from `distances_from_route` (no fresh location this
    tick) simply isn't evaluated — this dict only ever contains members
    app/route/service.py actually matched."""
    results = await detectors.detect_route_deviation(fake_redis, TRIP_ID, {"a": None}, THRESHOLDS, NOW)
    assert results[0].detected is False
