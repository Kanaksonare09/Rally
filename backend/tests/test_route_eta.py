"""app/route/eta.py — advanced (Phase 12) ETA: recent speed preferred over
baseline, stopped/extreme speeds ignored, and the group ETA's median-based
"representative member" behavior."""

import pytest

from app.intelligence.thresholds import Thresholds
from app.route.eta import EtaService

THRESHOLDS = Thresholds(
    stop_speed_mps=0.8, stop_duration_seconds=120, stale_location_seconds=60,
    falling_behind_distance_meters=500.0, falling_behind_duration_seconds=120,
    group_separation_distance_meters=800.0, group_separation_duration_seconds=120,
    isolated_member_distance_meters=1000.0, isolated_member_duration_seconds=120,
    max_reasonable_speed_mps=45.0, speed_anomaly_duration_seconds=20,
    group_cohesion_distance_meters=300.0, min_usable_accuracy_meters=100.0,
    evaluation_interval_seconds=3.0, route_endpoint_tolerance_meters=200.0,
    off_route_threshold_meters=100.0, route_deviation_duration_seconds=60,
    arrival_threshold_meters=50.0, arrival_duration_seconds=30,
    route_progress_stale_seconds=60, baseline_route_speed_mps=10.0,
)


# ---- single-member ETA ------------------------------------------------


def test_zero_remaining_distance_is_zero_eta():
    result = EtaService.calculate_eta(
        distance_remaining_meters=0.0, route_distance_meters=1000.0, route_estimated_duration_seconds=100,
        current_speed_mps=None, thresholds=THRESHOLDS,
    )
    assert result.eta_seconds == 0.0
    assert result.eta_available is True


def test_negative_remaining_distance_is_clamped_to_zero_eta():
    result = EtaService.calculate_eta(
        distance_remaining_meters=-5.0, route_distance_meters=1000.0, route_estimated_duration_seconds=100,
        current_speed_mps=None, thresholds=THRESHOLDS,
    )
    assert result.eta_seconds == 0.0


def test_usable_recent_speed_is_preferred_over_route_estimated_duration():
    # 100m remaining / 25 m/s = 4s — must win over the 10 m/s route average.
    result = EtaService.calculate_eta(
        distance_remaining_meters=100.0, route_distance_meters=1000.0, route_estimated_duration_seconds=100,
        current_speed_mps=25.0, thresholds=THRESHOLDS,
    )
    assert result.eta_seconds == pytest.approx(4.0)
    assert result.source == "recent_speed"
    assert result.eta_available is True


def test_stopped_speed_falls_back_instead_of_producing_a_huge_eta():
    """A near-zero speed reading must not be used directly (which would
    imply an absurdly large ETA) — falls back to route/baseline instead."""
    result = EtaService.calculate_eta(
        distance_remaining_meters=100.0, route_distance_meters=1000.0, route_estimated_duration_seconds=None,
        current_speed_mps=0.1, thresholds=THRESHOLDS,
    )
    assert result.source == "route_baseline"
    assert result.eta_seconds == pytest.approx(10.0)


def test_extreme_speed_is_ignored_as_a_sensor_glitch():
    result = EtaService.calculate_eta(
        distance_remaining_meters=100.0, route_distance_meters=1000.0, route_estimated_duration_seconds=None,
        current_speed_mps=999.0, thresholds=THRESHOLDS,
    )
    assert result.source == "route_baseline"


def test_uses_route_estimated_duration_when_available():
    # 1000m route declared to take 100s -> 10 m/s average -> 500m remaining -> 50s.
    result = EtaService.calculate_eta(
        distance_remaining_meters=500.0, route_distance_meters=1000.0, route_estimated_duration_seconds=100,
        current_speed_mps=None, thresholds=THRESHOLDS,
    )
    assert result.eta_seconds == pytest.approx(50.0)
    assert result.source == "route_estimated_duration"


def test_falls_back_to_baseline_speed_without_estimated_duration():
    result = EtaService.calculate_eta(
        distance_remaining_meters=100.0, route_distance_meters=1000.0, route_estimated_duration_seconds=None,
        current_speed_mps=None, thresholds=THRESHOLDS,
    )
    assert result.eta_seconds == pytest.approx(10.0)  # 100m / 10 m/s baseline
    assert result.source == "route_baseline"


def test_falls_back_to_baseline_when_estimated_duration_is_zero():
    result = EtaService.calculate_eta(
        distance_remaining_meters=100.0, route_distance_meters=1000.0, route_estimated_duration_seconds=0,
        current_speed_mps=None, thresholds=THRESHOLDS,
    )
    assert result.source == "route_baseline"


def test_unavailable_when_baseline_speed_is_non_positive():
    zero_speed_thresholds = Thresholds(**{**THRESHOLDS.__dict__, "baseline_route_speed_mps": 0.0})
    result = EtaService.calculate_eta(
        distance_remaining_meters=100.0, route_distance_meters=1000.0, route_estimated_duration_seconds=None,
        current_speed_mps=None, thresholds=zero_speed_thresholds,
    )
    assert result.eta_seconds is None
    assert result.eta_available is False
    assert result.source == "unavailable"


# ---- group ETA ----------------------------------------------------------


def test_group_eta_unavailable_with_no_members():
    result = EtaService.calculate_group_eta(
        members=[], route_distance_meters=1000.0, route_estimated_duration_seconds=None, thresholds=THRESHOLDS
    )
    assert result.eta_available is False
    assert result.eta_seconds is None


def test_group_eta_uses_median_remaining_distance_not_the_fastest():
    """Three members at 100m/500m/900m remaining, all moving at the same
    10 m/s — the median (500m) must drive the ETA, not the closest
    member's 100m (which would answer "when does the first person
    arrive," not "when does the group finish together")."""
    result = EtaService.calculate_group_eta(
        members=[(100.0, 10.0), (500.0, 10.0), (900.0, 10.0)],
        route_distance_meters=1000.0, route_estimated_duration_seconds=None, thresholds=THRESHOLDS,
    )
    assert result.eta_seconds == pytest.approx(50.0)  # 500m / 10 m/s


def test_group_eta_excludes_stopped_members_speed_but_not_their_distance():
    """A stopped member (speed below stop_speed_mps) still counts toward
    the group's representative remaining distance, but their near-zero
    speed must not drag the representative speed down."""
    result = EtaService.calculate_group_eta(
        members=[(200.0, 10.0), (200.0, 12.0), (200.0, 0.0)],
        route_distance_meters=1000.0, route_estimated_duration_seconds=None, thresholds=THRESHOLDS,
    )
    assert result.eta_seconds == pytest.approx(200.0 / 11.0)  # median of the two moving speeds (10, 12)


def test_group_eta_falls_back_when_the_whole_group_is_stopped():
    result = EtaService.calculate_group_eta(
        members=[(100.0, 0.0), (100.0, 0.2)],
        route_distance_meters=1000.0, route_estimated_duration_seconds=100, thresholds=THRESHOLDS,
    )
    assert result.source == "route_estimated_duration"
    assert result.eta_available is True


def test_group_eta_zero_when_group_has_arrived():
    result = EtaService.calculate_group_eta(
        members=[(0.0, 5.0), (0.0, 6.0)],
        route_distance_meters=1000.0, route_estimated_duration_seconds=None, thresholds=THRESHOLDS,
    )
    assert result.eta_seconds == 0.0
    assert result.eta_available is True
