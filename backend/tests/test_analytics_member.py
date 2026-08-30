"""app/analytics/member_analytics.py — per-member statistics, patched-
service-function pattern (no live database)."""

import uuid
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import patch

from app.analytics.member_analytics import build_member_analytics
from app.models.enums import TripStatus

TRIP_ID = uuid.uuid4()
GROUP_ID = uuid.uuid4()
USER_A = uuid.uuid4()
USER_B = uuid.uuid4()
T0 = datetime(2026, 8, 30, 10, 0, tzinfo=timezone.utc)


def make_trip(**overrides):
    trip = SimpleNamespace(id=TRIP_ID, group_id=GROUP_ID, status=TripStatus.COMPLETED, ended_at=T0)
    for k, v in overrides.items():
        setattr(trip, k, v)
    return trip


def _base_patches():
    return {
        "app.analytics.member_analytics.queries.list_active_group_members": [
            {"user_id": USER_A, "name": "Alice", "role": "LEADER", "joined_at": T0},
            {"user_id": USER_B, "name": "Bob", "role": "MEMBER", "joined_at": T0},
        ],
        "app.analytics.member_analytics.queries.fetch_location_points": {},
        "app.analytics.member_analytics.queries.fetch_movement_intervals_by_user": {},
        "app.analytics.member_analytics.route_service.get_route_by_trip": None,
        "app.analytics.member_analytics.queries.get_group_leader_id": USER_A,
        "app.analytics.member_analytics.intelligence_events.list_events": [],
        "app.analytics.member_analytics.alerts_service.list_alerts": [],
        "app.analytics.member_analytics.sos_service.list_sos": [],
    }


def _run(trip, overrides=None):
    values = _base_patches()
    if overrides:
        values.update(overrides)
    patchers = [patch(target, return_value=value) for target, value in values.items()]
    for p in patchers:
        p.start()
    try:
        return build_member_analytics(None, trip)
    finally:
        for p in patchers:
            p.stop()


def test_each_member_gets_its_own_row():
    result = _run(make_trip())
    assert len(result.members) == 2
    ids = {m.user_id for m in result.members}
    assert ids == {USER_A, USER_B}


def test_no_gps_data_is_null_distance():
    result = _run(make_trip())
    for member in result.members:
        assert member.distance_traveled_meters is None
        assert member.active_duration_seconds is None


def test_no_movement_events_reports_unavailable():
    result = _run(make_trip())
    for member in result.members:
        assert member.movement_duration_available is False
        assert member.moving_duration_seconds is None
        assert member.stopped_duration_seconds is None


def test_alerts_and_sos_counted_per_member_not_globally():
    overrides = {
        "app.analytics.member_analytics.alerts_service.list_alerts": [
            SimpleNamespace(user_id=USER_A), SimpleNamespace(user_id=USER_A), SimpleNamespace(user_id=USER_B)
        ],
        "app.analytics.member_analytics.sos_service.list_sos": [SimpleNamespace(user_id=USER_B)],
    }
    result = _run(make_trip(), overrides)

    alice = next(m for m in result.members if m.user_id == USER_A)
    bob = next(m for m in result.members if m.user_id == USER_B)

    assert alice.alerts_received == 2
    assert bob.alerts_received == 1
    assert alice.sos_triggered == 0
    assert bob.sos_triggered == 1


def test_route_deviations_counted_per_member():
    from app.models.enums import IntelligenceEventType

    overrides = {
        "app.analytics.member_analytics.intelligence_events.list_events": [
            SimpleNamespace(user_id=USER_A, event_type=IntelligenceEventType.ROUTE_DEVIATION)
        ],
    }
    result = _run(make_trip(), overrides)

    alice = next(m for m in result.members if m.user_id == USER_A)
    bob = next(m for m in result.members if m.user_id == USER_B)
    assert alice.route_deviations == 1
    assert bob.route_deviations == 0


def test_route_completion_null_when_no_route():
    result = _run(make_trip())
    for member in result.members:
        assert member.route_completion_percent is None
