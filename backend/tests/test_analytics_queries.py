"""
Pure-function tests for app/analytics/queries.py — no DB, no Redis. These
are the functions the zero-vs-null contract and GPS-filtering guarantees
actually live in, so they're tested directly and thoroughly.
"""

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest

from app.analytics import queries
from app.models.enums import TripStatus

T0 = datetime(2026, 8, 30, 10, 0, 0, tzinfo=timezone.utc)


def pt(lat, lon, accuracy, seconds_offset):
    return (lat, lon, accuracy, T0 + timedelta(seconds=seconds_offset))


# ---- compute_member_distance_meters: zero vs null --------------------------


def test_no_points_returns_none():
    assert queries.compute_member_distance_meters([], max_speed_mps=45.0, max_accuracy_meters=100.0) is None


def test_single_point_returns_zero_not_none():
    points = [pt(12.90, 77.0, 5.0, 0)]
    assert queries.compute_member_distance_meters(points, max_speed_mps=45.0, max_accuracy_meters=100.0) == 0.0


def test_all_points_filtered_by_bad_accuracy_returns_zero():
    points = [pt(12.90, 77.0, 500.0, 0), pt(12.905, 77.0, 500.0, 60)]
    assert queries.compute_member_distance_meters(points, max_speed_mps=45.0, max_accuracy_meters=100.0) == 0.0


def test_two_close_points_sum_a_real_distance():
    # ~555m apart (0.005 deg latitude), 60s apart -> ~9.25 m/s, plausible.
    points = [pt(12.900, 77.0, 5.0, 0), pt(12.905, 77.0, 5.0, 60)]
    distance = queries.compute_member_distance_meters(points, max_speed_mps=45.0, max_accuracy_meters=100.0)
    assert distance is not None
    assert 500 < distance < 600


def test_impossible_jump_is_excluded():
    """A GPS point implying an absurd speed (teleport / bad fix) must not
    be counted toward distance traveled."""
    points = [
        pt(12.900, 77.0, 5.0, 0),
        pt(15.000, 80.0, 5.0, 1),  # hundreds of km in 1 second
        pt(12.901, 77.0, 5.0, 61),
    ]
    distance = queries.compute_member_distance_meters(points, max_speed_mps=45.0, max_accuracy_meters=100.0)
    # Only the plausible first->third segment should be counted; the
    # teleport point contributes nothing.
    assert distance is not None
    assert distance < 500


def test_bad_accuracy_point_is_skipped_not_just_its_segment():
    """The anchor stays on the last *good* point — a single noisy point
    in the middle must not poison the segment on either side of it."""
    points = [
        pt(12.900, 77.0, 5.0, 0),
        pt(12.950, 77.0, 500.0, 30),  # noisy — should be dropped entirely
        pt(12.905, 77.0, 5.0, 60),
    ]
    distance = queries.compute_member_distance_meters(points, max_speed_mps=45.0, max_accuracy_meters=100.0)
    # Should reflect point1 -> point3 directly (~555m), not include any
    # jump to/from the noisy middle point.
    assert distance is not None
    assert 500 < distance < 600


def test_out_of_order_duplicate_timestamp_segment_is_skipped():
    points = [pt(12.900, 77.0, 5.0, 0), pt(12.901, 77.0, 5.0, 0)]  # same timestamp
    distance = queries.compute_member_distance_meters(points, max_speed_mps=45.0, max_accuracy_meters=100.0)
    assert distance == 0.0


def test_max_accuracy_none_disables_the_accuracy_filter():
    points = [pt(12.900, 77.0, 9999.0, 0), pt(12.905, 77.0, 9999.0, 60)]
    distance = queries.compute_member_distance_meters(points, max_speed_mps=45.0, max_accuracy_meters=None)
    assert distance is not None and distance > 0


# ---- compute_distances_by_user ---------------------------------------------


def test_compute_distances_by_user_drops_members_with_no_gps():
    points_by_user = {"a": [pt(12.9, 77.0, 5.0, 0), pt(12.905, 77.0, 5.0, 60)], "b": []}
    result = queries.compute_distances_by_user(points_by_user, max_speed_mps=45.0, max_accuracy_meters=100.0)
    assert "a" in result
    assert "b" not in result


# ---- compute_active_duration_seconds ---------------------------------------


def test_active_duration_none_with_fewer_than_two_points():
    assert queries.compute_active_duration_seconds([pt(12.9, 77.0, 5.0, 0)]) is None
    assert queries.compute_active_duration_seconds([]) is None


def test_active_duration_spans_first_to_last_point():
    points = [pt(12.9, 77.0, 5.0, 0), pt(12.91, 77.0, 5.0, 3600)]
    assert queries.compute_active_duration_seconds(points) == 3600.0


# ---- pick_representative_value ---------------------------------------------


def test_representative_value_empty_is_none():
    assert queries.pick_representative_value({}, leader_id=None) is None


def test_representative_value_prefers_leader():
    values = {"leader": 100.0, "member": 900.0}
    result = queries.pick_representative_value(values, leader_id="leader")
    assert result == 100.0


def test_representative_value_falls_back_to_median_without_leader_data():
    values = {"a": 100.0, "b": 200.0, "c": 900.0}
    result = queries.pick_representative_value(values, leader_id="not-in-values")
    assert result == 200.0


def test_representative_value_resists_a_single_outlier():
    values = {"a": 100.0, "b": 110.0, "c": 9000.0}
    result = queries.pick_representative_value(values, leader_id=None)
    assert result == 110.0


# ---- compute_movement_durations ---------------------------------------------


def test_no_intervals_means_unavailable_not_zero():
    available, moving, stopped = queries.compute_movement_durations([], trip_end=T0)
    assert available is False
    assert moving is None
    assert stopped is None


def test_movement_durations_sum_by_state():
    intervals = [
        ("MOVING", T0, T0 + timedelta(seconds=100)),
        ("STOPPED", T0 + timedelta(seconds=100), T0 + timedelta(seconds=150)),
        ("MOVING", T0 + timedelta(seconds=150), T0 + timedelta(seconds=250)),
    ]
    available, moving, stopped = queries.compute_movement_durations(intervals, trip_end=T0 + timedelta(seconds=250))
    assert available is True
    assert moving == 200.0
    assert stopped == 50.0


def test_open_interval_closed_at_trip_end():
    intervals = [("MOVING", T0, None)]
    trip_end = T0 + timedelta(seconds=500)
    available, moving, stopped = queries.compute_movement_durations(intervals, trip_end=trip_end)
    assert available is True
    assert moving == 500.0
    assert stopped == 0.0


# ---- compute_trip_duration_seconds -----------------------------------------


def make_trip(**overrides):
    trip = SimpleNamespace(status=TripStatus.CREATED, started_at=None, ended_at=None)
    for k, v in overrides.items():
        setattr(trip, k, v)
    return trip


def test_duration_none_for_never_started_trip():
    trip = make_trip(status=TripStatus.CREATED, started_at=None)
    assert queries.compute_trip_duration_seconds(trip) is None


def test_duration_none_for_cancelled_before_start():
    trip = make_trip(status=TripStatus.CANCELLED, started_at=None)
    assert queries.compute_trip_duration_seconds(trip) is None


def test_duration_for_completed_trip_uses_stored_timestamps():
    trip = make_trip(status=TripStatus.COMPLETED, started_at=T0, ended_at=T0 + timedelta(hours=2))
    assert queries.compute_trip_duration_seconds(trip) == 7200


def test_duration_for_active_trip_uses_now():
    trip = make_trip(status=TripStatus.ACTIVE, started_at=datetime.now(timezone.utc) - timedelta(seconds=30))
    duration = queries.compute_trip_duration_seconds(trip)
    assert duration is not None
    assert 25 <= duration <= 40


def test_duration_never_negative_even_with_bad_timestamps():
    trip = make_trip(status=TripStatus.COMPLETED, started_at=T0, ended_at=T0 - timedelta(seconds=10))
    assert queries.compute_trip_duration_seconds(trip) == 0
