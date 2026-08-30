"""
app/analytics/replay.py — sampling, carry-forward positions, movement
state lookup, route-progress matching, and the frame-count ceiling. All
collaborators (queries, timeline, route matching) are patched at the
point replay.py imports them, same pattern as test_analytics_dashboard.py.
"""

import uuid
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import patch

from app.analytics.replay import build_replay
from app.core.config import settings

TRIP_ID = uuid.uuid4()
GROUP_ID = uuid.uuid4()
USER_A = str(uuid.uuid4())
USER_B = str(uuid.uuid4())
BASE = datetime(2026, 8, 31, 12, 0, 0, tzinfo=timezone.utc)


def make_trip(**overrides):
    trip = SimpleNamespace(id=TRIP_ID, group_id=GROUP_ID, started_at=BASE, ended_at=None, status="ACTIVE")
    for k, v in overrides.items():
        setattr(trip, k, v)
    return trip


def pt(lat, lon, seconds_offset, accuracy=5.0):
    return (lat, lon, accuracy, BASE + timedelta(seconds=seconds_offset))


def _patched(points_by_user, movement_by_user=None, route=None, events=None):
    return (
        patch("app.analytics.replay.queries.fetch_location_points", return_value=points_by_user),
        patch("app.analytics.replay.queries.fetch_movement_intervals_by_user", return_value=movement_by_user or {}),
        patch("app.analytics.replay.queries.get_group_leader_id", return_value=None),
        patch("app.analytics.replay.route_service.get_route_by_trip", return_value=route),
        patch("app.analytics.replay.timeline_module.build_timeline", return_value=events or []),
    )


def test_no_gps_data_returns_empty_timeline():
    with _patched({})[0], _patched({})[1], _patched({})[2], _patched({})[3], _patched({})[4]:
        result = build_replay(db=None, trip=make_trip())
    assert result.timeline == []
    assert result.total_distance_meters is None


def test_single_member_carries_position_forward_between_samples():
    points = {USER_A: [pt(0.0, 0.0, 0), pt(0.0, 0.001, 20)]}
    p1, p2, p3, p4, p5 = _patched(points)
    with p1, p2, p3, p4, p5:
        result = build_replay(db=None, trip=make_trip(), interval_seconds=10)

    # Frames at t=0,10,20 — the t=10 frame carries forward the t=0 point
    # (no interpolation), the t=20 frame picks up the second real point.
    assert len(result.timeline) == 3
    assert result.timeline[0].members[0].latitude == 0.0
    assert result.timeline[1].members[0].longitude == 0.0  # still the first point, carried forward
    assert result.timeline[2].members[0].longitude == 0.001


def test_member_absent_before_their_first_point():
    points = {
        USER_A: [pt(0.0, 0.0, 0)],
        USER_B: [pt(0.0, 0.0, 30)],  # doesn't start until t=30
    }
    p1, p2, p3, p4, p5 = _patched(points)
    with p1, p2, p3, p4, p5:
        result = build_replay(db=None, trip=make_trip(), interval_seconds=10)

    first_frame_users = {str(m.user_id) for m in result.timeline[0].members}
    assert first_frame_users == {USER_A}
    last_frame_users = {str(m.user_id) for m in result.timeline[-1].members}
    assert last_frame_users == {USER_A, USER_B}


def test_movement_state_comes_from_persisted_intervals():
    points = {USER_A: [pt(0.0, 0.0, 0)]}
    movement = {USER_A: [("MOVING", BASE, None)]}
    p1, p2, p3, p4, p5 = _patched(points, movement_by_user=movement)
    with p1, p2, p3, p4, p5:
        result = build_replay(db=None, trip=make_trip(), interval_seconds=10)

    assert result.timeline[0].members[0].movement_state == "MOVING"


def test_no_movement_interval_covering_the_point_is_null_not_fabricated():
    points = {USER_A: [pt(0.0, 0.0, 0)]}
    p1, p2, p3, p4, p5 = _patched(points, movement_by_user={})
    with p1, p2, p3, p4, p5:
        result = build_replay(db=None, trip=make_trip(), interval_seconds=10)

    assert result.timeline[0].members[0].movement_state is None


def test_route_progress_computed_when_route_available():
    points = {USER_A: [pt(0.0, 0.0, 0)]}
    route = SimpleNamespace(coordinates=[[0.0, 0.0], [0.0, 0.01]])
    p1, p2, p3, p4, p5 = _patched(points, route=route)
    with p1, p2, p3, p4, p5:
        result = build_replay(db=None, trip=make_trip(), interval_seconds=10)

    assert result.timeline[0].members[0].route_progress is not None
    assert 0.0 <= result.timeline[0].members[0].route_progress <= 1.0


def test_no_route_leaves_route_progress_null():
    points = {USER_A: [pt(0.0, 0.0, 0)]}
    p1, p2, p3, p4, p5 = _patched(points, route=None)
    with p1, p2, p3, p4, p5:
        result = build_replay(db=None, trip=make_trip(), interval_seconds=10)

    assert result.timeline[0].members[0].route_progress is None


def test_interval_seconds_clamped_to_configured_bounds():
    points = {USER_A: [pt(0.0, 0.0, 0)]}
    p1, p2, p3, p4, p5 = _patched(points)
    with p1, p2, p3, p4, p5:
        too_small = build_replay(db=None, trip=make_trip(), interval_seconds=0)
        too_large = build_replay(db=None, trip=make_trip(), interval_seconds=999999)

    assert too_small.interval_seconds == settings.REPLAY_MIN_INTERVAL_SECONDS
    assert too_large.interval_seconds == settings.REPLAY_MAX_INTERVAL_SECONDS


def test_frame_count_never_exceeds_the_configured_ceiling(monkeypatch):
    monkeypatch.setattr(settings, "REPLAY_MAX_FRAMES", 5)
    # A long trip sampled finely would naively produce many more than 5 frames.
    points = {USER_A: [pt(0.0, 0.0, 0), pt(0.0, 0.01, 3600)]}
    p1, p2, p3, p4, p5 = _patched(points)
    with p1, p2, p3, p4, p5:
        result = build_replay(db=None, trip=make_trip(), interval_seconds=1)

    assert len(result.timeline) <= 5 + 1  # +1 tolerance for the final boundary frame


def test_events_reused_from_timeline_module():
    from app.schemas.analytics import TimelineEvent

    events = [TimelineEvent(type="TRIP_STARTED", timestamp=BASE, data={})]
    p1, p2, p3, p4, p5 = _patched({}, events=events)
    with p1, p2, p3, p4, p5:
        result = build_replay(db=None, trip=make_trip())

    assert result.events == events


def test_total_distance_uses_representative_value():
    points = {USER_A: [pt(0.0, 0.0, 0), pt(0.0, 0.01, 60)]}
    p1, p2, p3, p4, p5 = _patched(points)
    with p1, p2, p3, p4, p5:
        result = build_replay(db=None, trip=make_trip())

    assert result.total_distance_meters is not None
    assert result.total_distance_meters > 0
