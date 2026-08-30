"""
Typed snapshot of every intelligence threshold, read from app.core.config
once per evaluation instead of scattering `settings.X` references through
detectors.py/engine.py/group_analysis.py callers. Also makes thresholds
trivial for tests to override (monkeypatch `settings.X`, same established
pattern as the rest of this codebase) without reaching into every function
signature.
"""

from dataclasses import dataclass

from app.core.config import settings as _settings


@dataclass(frozen=True)
class Thresholds:
    stop_speed_mps: float
    stop_duration_seconds: int
    stale_location_seconds: int
    falling_behind_distance_meters: float
    falling_behind_duration_seconds: int
    group_separation_distance_meters: float
    group_separation_duration_seconds: int
    isolated_member_distance_meters: float
    isolated_member_duration_seconds: int
    max_reasonable_speed_mps: float
    speed_anomaly_duration_seconds: int
    group_cohesion_distance_meters: float
    min_usable_accuracy_meters: float
    evaluation_interval_seconds: float
    # --- Route intelligence (Phase 9) ---
    route_endpoint_tolerance_meters: float
    off_route_threshold_meters: float
    route_deviation_duration_seconds: int
    arrival_threshold_meters: float
    arrival_duration_seconds: int
    route_progress_stale_seconds: int
    baseline_route_speed_mps: float


def current_thresholds() -> Thresholds:
    """Reads the live `settings` object on every call, so tests that
    monkeypatch `settings.X` still take effect, while a single evaluation
    works from one consistent snapshot rather than re-reading settings
    mid-calculation."""
    s = _settings
    return Thresholds(
        stop_speed_mps=s.STOP_SPEED_MPS,
        stop_duration_seconds=s.STOP_DURATION_SECONDS,
        stale_location_seconds=s.STALE_LOCATION_SECONDS,
        falling_behind_distance_meters=s.FALLING_BEHIND_DISTANCE_METERS,
        falling_behind_duration_seconds=s.FALLING_BEHIND_DURATION_SECONDS,
        group_separation_distance_meters=s.GROUP_SEPARATION_DISTANCE_METERS,
        group_separation_duration_seconds=s.GROUP_SEPARATION_DURATION_SECONDS,
        isolated_member_distance_meters=s.ISOLATED_MEMBER_DISTANCE_METERS,
        isolated_member_duration_seconds=s.ISOLATED_MEMBER_DURATION_SECONDS,
        max_reasonable_speed_mps=s.MAX_REASONABLE_SPEED_MPS,
        speed_anomaly_duration_seconds=s.SPEED_ANOMALY_DURATION_SECONDS,
        group_cohesion_distance_meters=s.GROUP_COHESION_DISTANCE_METERS,
        min_usable_accuracy_meters=s.MIN_USABLE_ACCURACY_METERS,
        evaluation_interval_seconds=s.INTELLIGENCE_EVALUATION_INTERVAL_SECONDS,
        route_endpoint_tolerance_meters=s.ROUTE_ENDPOINT_TOLERANCE_METERS,
        off_route_threshold_meters=s.OFF_ROUTE_THRESHOLD_METERS,
        route_deviation_duration_seconds=s.ROUTE_DEVIATION_DURATION_SECONDS,
        arrival_threshold_meters=s.ARRIVAL_THRESHOLD_METERS,
        arrival_duration_seconds=s.ARRIVAL_DURATION_SECONDS,
        route_progress_stale_seconds=s.ROUTE_PROGRESS_STALE_SECONDS,
        baseline_route_speed_mps=s.BASELINE_ROUTE_SPEED_MPS,
    )
