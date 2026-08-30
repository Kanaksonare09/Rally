"""
End-to-end analytics integration test: one shared fake DB session (no
live Postgres — see the FakeSession below, which discriminates by ORM
entity the same way test_intelligence_engine_route.py/test_analytics_route.py
do) carrying a realistic small trip — a leader who completes the route, a
member who partially completes it, one resolved ROUTE_DEVIATION, one
active FALLING_BEHIND, one alert, no SOS — through trip/member/safety
analytics, snapshot generation (twice, to prove idempotency), and
confirms every module agrees with the others on the same underlying data
(no cross-module drift), plus the null-vs-zero contract holds throughout.
"""

import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import app.models  # noqa: F401 — registers every model before instantiation
from app.analytics import member_analytics, safety_analytics, snapshot as snapshot_module
from app.analytics import trip_analytics as trip_analytics_module
from app.models.alert import Alert
from app.models.enums import (
    AlertSeverity,
    AlertStatus,
    AlertType,
    IntelligenceEventType,
    IntelligenceSeverity,
    MemberRole,
    MemberStatus,
    RouteStatus,
    TripStatus,
)
from app.models.group_member import GroupMember
from app.models.intelligence_event import IntelligenceEvent
from app.models.location_history import LocationHistory
from app.models.profile import Profile
from app.models.route import Route
from app.models.sos_event import SOSEvent
from app.models.trip import Trip
from app.models.trip_analytics_snapshot import TripAnalyticsSnapshot

TRIP_ID = uuid.uuid4()
GROUP_ID = uuid.uuid4()
LEADER_ID = uuid.uuid4()
MEMBER_ID = uuid.uuid4()
T0 = datetime(2026, 8, 30, 9, 0, 0, tzinfo=timezone.utc)


class _Result:
    def __init__(self, rows):
        self._rows = rows

    def all(self):
        return self._rows


class _ScalarResult:
    def __init__(self, single=None, many=None):
        self._single = single
        self._many = many if many is not None else []

    def first(self):
        return self._single

    def all(self):
        return self._many


class IntegrationFakeSession:
    def __init__(self):
        self.route = None
        self.location_rows = []
        self.group_member_profile_rows = []
        self.leader_member = None
        self.intelligence_events = []
        self.alerts = []
        self.sos_events = []
        self.snapshot = None
        self.commits = 0

    def execute(self, stmt):
        entity = stmt.column_descriptions[0]["entity"]
        if entity is GroupMember:
            return _Result(self.group_member_profile_rows)
        if entity is LocationHistory:
            return _Result(self.location_rows)
        return _Result([])

    def scalars(self, stmt):
        entity = stmt.column_descriptions[0]["entity"]
        if entity is Route:
            return _ScalarResult(single=self.route)
        if entity is Alert:
            return _ScalarResult(many=self.alerts)
        if entity is SOSEvent:
            return _ScalarResult(many=self.sos_events)
        if entity is GroupMember:
            return _ScalarResult(single=self.leader_member)
        if entity is TripAnalyticsSnapshot:
            return _ScalarResult(single=self.snapshot)
        return _ScalarResult()

    def add(self, obj):
        if isinstance(obj, TripAnalyticsSnapshot):
            self.snapshot = obj

    def commit(self):
        self.commits += 1

    def refresh(self, obj):
        if getattr(obj, "id", None) is None:
            obj.id = uuid.uuid4()

    def rollback(self):
        pass


def build_fixture() -> tuple:
    trip = Trip(
        id=TRIP_ID, group_id=GROUP_ID, status=TripStatus.COMPLETED,
        started_at=T0, ended_at=T0 + timedelta(hours=1),
    )

    route = Route(
        id=uuid.uuid4(), trip_id=TRIP_ID,
        origin_latitude=12.900, origin_longitude=77.0,
        destination_latitude=12.920, destination_longitude=77.0,
        coordinates=[[77.0, 12.900], [77.0, 12.920]],
        distance_meters=2224.0, estimated_duration_seconds=1800, status=RouteStatus.COMPLETED,
    )

    leader_member = GroupMember(id=uuid.uuid4(), group_id=GROUP_ID, user_id=LEADER_ID, role=MemberRole.LEADER, status=MemberStatus.ACTIVE, joined_at=T0)
    member_member = GroupMember(id=uuid.uuid4(), group_id=GROUP_ID, user_id=MEMBER_ID, role=MemberRole.MEMBER, status=MemberStatus.ACTIVE, joined_at=T0)
    leader_profile = Profile(id=LEADER_ID, full_name="Leader Lin")
    member_profile = Profile(id=MEMBER_ID, full_name="Member Max")

    # Leader travels the full route.
    leader_points = [
        (LEADER_ID, 12.900, 77.0, 5.0, T0),
        (LEADER_ID, 12.910, 77.0, 5.0, T0 + timedelta(minutes=15)),
        (LEADER_ID, 12.920, 77.0, 5.0, T0 + timedelta(minutes=30)),
    ]
    # Member only makes it about halfway.
    member_points = [
        (MEMBER_ID, 12.900, 77.0, 5.0, T0),
        (MEMBER_ID, 12.910, 77.0, 5.0, T0 + timedelta(minutes=30)),
    ]

    falling_behind = IntelligenceEvent(
        id=uuid.uuid4(), trip_id=TRIP_ID, group_id=GROUP_ID,
        event_type=IntelligenceEventType.FALLING_BEHIND, severity=IntelligenceSeverity.WARNING,
        user_id=MEMBER_ID, related_user_id=None, event_metadata={"distance_meters": 650},
        detected_at=T0 + timedelta(minutes=10), resolved_at=None,  # still active
    )
    route_deviation = IntelligenceEvent(
        id=uuid.uuid4(), trip_id=TRIP_ID, group_id=GROUP_ID,
        event_type=IntelligenceEventType.ROUTE_DEVIATION, severity=IntelligenceSeverity.WARNING,
        user_id=MEMBER_ID, related_user_id=None, event_metadata={"distance_from_route_meters": 180.0},
        detected_at=T0 + timedelta(minutes=20), resolved_at=T0 + timedelta(minutes=25),  # resolved
    )

    alert = Alert(
        id=uuid.uuid4(), group_id=GROUP_ID, trip_id=TRIP_ID, event_id=falling_behind.id,
        alert_type=AlertType.FALLING_BEHIND, severity=AlertSeverity.WARNING, status=AlertStatus.ACTIVE,
        user_id=MEMBER_ID, related_user_id=None, title="Member falling behind",
        message="A group member is falling behind (650m from the group).", alert_metadata={"distance_meters": 650},
        created_at=T0 + timedelta(minutes=10),
    )

    session = IntegrationFakeSession()
    session.route = route
    session.leader_member = leader_member
    session.group_member_profile_rows = [(leader_member, leader_profile), (member_member, member_profile)]
    session.location_rows = leader_points + member_points
    session.intelligence_events = [falling_behind, route_deviation]
    session.alerts = [alert]
    session.sos_events = []

    return session, trip


def _fake_list_events(db: "IntegrationFakeSession"):
    """intelligence_events.list_events() is called with different
    event_type filters by different analytics modules within the same
    test (ROUTE_DEVIATION-only from route/member/trip analytics, no
    filter at all from safety analytics) — a plain entity-dispatch fake
    can't distinguish those the way the Route/Alert/SOSEvent fakes above
    can, so this replaces the real function directly for the duration of
    each test, matching its real (db, trip_id, *, event_type=None, ...)
    calling convention exactly."""

    def _impl(_db, _trip_id, *, event_type=None, **_kwargs):
        if event_type is not None:
            return [e for e in db.intelligence_events if e.event_type == event_type]
        return list(db.intelligence_events)

    return _impl


def test_full_trip_analytics_pipeline_is_internally_consistent():
    db, trip = build_fixture()

    with patch("app.intelligence.events.list_events", side_effect=_fake_list_events(db)):
        trip_result = trip_analytics_module.compute_trip_analytics(db, trip)
        member_result = member_analytics.build_member_analytics(db, trip)
        safety_result = safety_analytics.build_safety_analytics(db, trip)

    # --- trip-level ---
    assert trip_result.member_count == 2
    assert trip_result.duration_seconds == 3600
    assert trip_result.route_available is True
    assert trip_result.distance_traveled_meters is not None and trip_result.distance_traveled_meters > 0
    assert trip_result.alerts_count == 1
    assert trip_result.sos_count == 0  # genuinely zero
    assert trip_result.route_deviations == 1

    # --- member-level: leader traveled further than the member who
    # turned back partway, and only the member has a deviation/alert. ---
    leader_item = next(m for m in member_result.members if m.user_id == LEADER_ID)
    member_item = next(m for m in member_result.members if m.user_id == MEMBER_ID)

    assert leader_item.distance_traveled_meters > member_item.distance_traveled_meters
    assert leader_item.route_deviations == 0
    assert member_item.route_deviations == 1
    assert leader_item.alerts_received == 0
    assert member_item.alerts_received == 1
    # Leader reached the destination; the member did not.
    assert leader_item.route_completion_percent > member_item.route_completion_percent
    assert leader_item.route_completion_percent == 100.0

    # --- safety-level: must agree with trip-level counts exactly ---
    assert safety_result.alerts.total == trip_result.alerts_count
    assert safety_result.intelligence_events.total == 2  # FALLING_BEHIND + ROUTE_DEVIATION
    assert safety_result.intelligence_events.resolved == 1
    assert safety_result.intelligence_events.active == 1
    assert safety_result.sos.total == 0


def test_snapshot_generation_then_idempotent_reuse():
    db, trip = build_fixture()

    with patch("app.intelligence.events.list_events", side_effect=_fake_list_events(db)):
        first = snapshot_module.generate_snapshot(db, trip)
        assert db.commits == 1
        assert first.distance_traveled_meters is not None
        assert first.alerts_count == 1
        assert first.route_deviations == 1

        second = snapshot_module.generate_snapshot(db, trip)

    assert second is first
    assert db.commits == 1  # no second INSERT


def test_snapshot_matches_live_trip_analytics():
    db, trip = build_fixture()

    with patch("app.intelligence.events.list_events", side_effect=_fake_list_events(db)):
        live = trip_analytics_module.compute_trip_analytics(db, trip, source="live")
        snap = snapshot_module.generate_snapshot(db, trip)

    from_snapshot = snapshot_module.snapshot_to_trip_analytics(trip, snap)

    assert from_snapshot.duration_seconds == live.duration_seconds
    assert from_snapshot.member_count == live.member_count
    assert from_snapshot.alerts_count == live.alerts_count
    assert from_snapshot.route_deviations == live.route_deviations
    assert from_snapshot.source == "snapshot"
    assert live.source == "live"


def test_no_sos_in_this_trip_is_zero_not_null():
    db, trip = build_fixture()
    with patch("app.intelligence.events.list_events", side_effect=_fake_list_events(db)):
        result = trip_analytics_module.compute_trip_analytics(db, trip)
    assert result.sos_count == 0
    assert result.sos_count is not None
