"""
app/analytics/route_analytics.py — route completion/deviation statistics,
against a fake DB session (no live database) discriminating by which ORM
entity a query selects, same trick as test_intelligence_engine_route.py.
"""

import uuid
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest

import app.models  # noqa: F401 — registers every model before instantiation
from app.analytics import route_analytics
from app.models.enums import IntelligenceEventType, IntelligenceSeverity, RouteStatus
from app.models.intelligence_event import IntelligenceEvent
from app.models.route import Route
from app.models.trip import Trip

TRIP_ID = uuid.uuid4()
GROUP_ID = uuid.uuid4()
USER_A = str(uuid.uuid4())
USER_B = str(uuid.uuid4())
T0 = datetime(2026, 8, 30, 10, 0, 0, tzinfo=timezone.utc)


class _ScalarResult:
    def __init__(self, single=None, many=None):
        self._single = single
        self._many = many or []

    def first(self):
        return self._single

    def all(self):
        return self._many


class FakeSession:
    def __init__(self, route=None, deviation_events=None):
        self._route = route
        self._deviation_events = deviation_events or []

    def scalars(self, stmt):
        entity = stmt.column_descriptions[0]["entity"]
        if entity is Route:
            return _ScalarResult(single=self._route)
        if entity is IntelligenceEvent:
            return _ScalarResult(many=self._deviation_events)
        return _ScalarResult()

    def execute(self, stmt):
        return _ScalarResult(many=[])


def make_route(**overrides) -> Route:
    route = Route(
        id=uuid.uuid4(), trip_id=TRIP_ID, name="Test route",
        origin_latitude=12.90, origin_longitude=77.0,
        destination_latitude=12.91, destination_longitude=77.0,
        coordinates=[[77.0, 12.90], [77.0, 12.91]],
        distance_meters=1112.0, estimated_duration_seconds=600, status=RouteStatus.ACTIVE,
    )
    for k, v in overrides.items():
        setattr(route, k, v)
    return route


def make_trip(**overrides) -> Trip:
    trip = Trip(id=TRIP_ID, group_id=GROUP_ID)
    for k, v in overrides.items():
        setattr(trip, k, v)
    return trip


def make_deviation_event(distance_from_route_meters, resolved=False, user_id=USER_A) -> IntelligenceEvent:
    return IntelligenceEvent(
        id=uuid.uuid4(), trip_id=TRIP_ID, group_id=GROUP_ID,
        event_type=IntelligenceEventType.ROUTE_DEVIATION, severity=IntelligenceSeverity.WARNING,
        user_id=uuid.UUID(user_id), related_user_id=None,
        event_metadata={"distance_from_route_meters": distance_from_route_meters, "threshold_meters": 100.0},
        detected_at=T0, resolved_at=T0 + timedelta(minutes=5) if resolved else None,
    )


# ---- compute_route_completion ----------------------------------------------


def test_completion_none_with_no_points():
    route = make_route()
    percent, remaining, arrived = route_analytics.compute_route_completion(route, {}, leader_id=None)
    assert percent is None and remaining is None and arrived is None


def test_completion_at_destination_is_full_and_arrived():
    route = make_route()
    points = {USER_A: [(12.91, 77.0, 5.0, T0)]}
    percent, remaining, arrived = route_analytics.compute_route_completion(route, points, leader_id=None)
    assert percent == pytest.approx(100.0, abs=1.0)
    assert arrived is True


def test_completion_at_origin_is_zero_and_not_arrived():
    route = make_route()
    points = {USER_A: [(12.90, 77.0, 5.0, T0)]}
    percent, remaining, arrived = route_analytics.compute_route_completion(route, points, leader_id=None)
    assert percent == pytest.approx(0.0, abs=1.0)
    assert arrived is False


def test_completion_uses_leader_when_available():
    route = make_route()
    points = {
        USER_A: [(12.91, 77.0, 5.0, T0)],  # leader: at destination
        USER_B: [(12.90, 77.0, 5.0, T0)],  # member: at origin
    }
    percent, _remaining, arrived = route_analytics.compute_route_completion(route, points, leader_id=uuid.UUID(USER_A))
    assert percent == pytest.approx(100.0, abs=1.0)
    assert arrived is True


def test_completion_falls_back_to_median_without_leader_data():
    route = make_route()
    points = {
        USER_A: [(12.905, 77.0, 5.0, T0)],  # ~midpoint
        USER_B: [(12.90, 77.0, 5.0, T0)],  # origin
    }
    percent, _remaining, _arrived = route_analytics.compute_route_completion(
        route, points, leader_id=uuid.uuid4()  # leader has no points at all
    )
    assert percent is not None
    assert 0.0 < percent < 100.0


# ---- build_route_analytics --------------------------------------------------


def test_no_route_reports_unavailable_not_fake_zeros():
    db = FakeSession(route=None)
    trip = make_trip()
    result = route_analytics.build_route_analytics(db, trip, points_by_user={}, leader_id=None)
    assert result.route_available is False
    assert result.planned_distance_meters is None
    assert result.route_deviations == 0


def test_route_analytics_counts_resolved_and_active_deviations():
    db = FakeSession(
        route=make_route(),
        deviation_events=[
            make_deviation_event(150.0, resolved=True),
            make_deviation_event(300.0, resolved=False),
        ],
    )
    trip = make_trip()
    result = route_analytics.build_route_analytics(
        db, trip, points_by_user={USER_A: [(12.90, 77.0, 5.0, T0)]}, leader_id=None
    )
    assert result.route_available is True
    assert result.route_deviations == 2
    assert result.resolved_deviations == 1
    assert result.active_deviations == 1
    assert result.average_distance_from_route_meters == pytest.approx(225.0)
    assert result.maximum_distance_from_route_meters == pytest.approx(300.0)


def test_no_deviation_events_returns_null_averages_not_zero():
    db = FakeSession(route=make_route(), deviation_events=[])
    trip = make_trip()
    result = route_analytics.build_route_analytics(db, trip, points_by_user={}, leader_id=None)
    assert result.route_deviations == 0
    assert result.average_distance_from_route_meters is None
    assert result.maximum_distance_from_route_meters is None


# ---- match_last_point --------------------------------------------------


def test_match_last_point_none_with_no_points():
    assert route_analytics.match_last_point(make_route(), []) is None


def test_match_last_point_uses_the_most_recent_point():
    route = make_route()
    points = [(12.90, 77.0, 5.0, T0), (12.905, 77.0, 5.0, T0 + timedelta(seconds=60))]
    match = route_analytics.match_last_point(route, points)
    assert match is not None
    assert match.route_fraction == pytest.approx(0.5, abs=0.02)
