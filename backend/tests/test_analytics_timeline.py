"""app/analytics/timeline.py — chronological event combination, patched
service-function pattern (no live database)."""

import uuid
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import patch

from app.analytics.timeline import build_timeline
from app.models.enums import IntelligenceEventType, IntelligenceSeverity, RouteStatus, TripStatus

TRIP_ID = uuid.uuid4()
T0 = datetime(2026, 8, 30, 10, 0, 0, tzinfo=timezone.utc)


def make_trip(**overrides):
    trip = SimpleNamespace(id=TRIP_ID, status=TripStatus.COMPLETED, started_at=T0, ended_at=T0 + timedelta(hours=1), updated_at=T0)
    for k, v in overrides.items():
        setattr(trip, k, v)
    return trip


def make_event(event_type, detected_at, resolved_at=None):
    return SimpleNamespace(
        event_type=event_type, detected_at=detected_at, resolved_at=resolved_at,
        user_id=None, related_user_id=None, severity=IntelligenceSeverity.WARNING, event_metadata={},
    )


def make_alert(created_at, resolved_at=None):
    from app.models.enums import AlertSeverity, AlertType

    return SimpleNamespace(
        id=uuid.uuid4(), created_at=created_at, resolved_at=resolved_at,
        alert_type=AlertType.FALLING_BEHIND, severity=AlertSeverity.WARNING, user_id=None,
    )


def make_sos(triggered_at, resolved_at=None):
    return SimpleNamespace(id=uuid.uuid4(), triggered_at=triggered_at, resolved_at=resolved_at, user_id=None)


@patch("app.analytics.timeline.sos_service.list_sos")
@patch("app.analytics.timeline.alerts_service.list_alerts")
@patch("app.analytics.timeline.intelligence_events.list_events")
@patch("app.analytics.timeline.route_service.get_route_by_trip")
def test_events_are_sorted_chronologically(mock_route, mock_events, mock_alerts, mock_sos):
    mock_route.return_value = None
    mock_events.return_value = [make_event(IntelligenceEventType.FALLING_BEHIND, T0 + timedelta(minutes=30))]
    mock_alerts.return_value = [make_alert(T0 + timedelta(minutes=10))]
    mock_sos.return_value = [make_sos(T0 + timedelta(minutes=20))]

    trip = make_trip()
    events = build_timeline(None, trip)

    timestamps = [e.timestamp for e in events]
    assert timestamps == sorted(timestamps)


@patch("app.analytics.timeline.sos_service.list_sos")
@patch("app.analytics.timeline.alerts_service.list_alerts")
@patch("app.analytics.timeline.intelligence_events.list_events")
@patch("app.analytics.timeline.route_service.get_route_by_trip")
def test_trip_started_and_completed_included(mock_route, mock_events, mock_alerts, mock_sos):
    mock_route.return_value = None
    mock_events.return_value = []
    mock_alerts.return_value = []
    mock_sos.return_value = []

    trip = make_trip(status=TripStatus.COMPLETED)
    events = build_timeline(None, trip)
    types = [e.type for e in events]

    assert "TRIP_STARTED" in types
    assert "TRIP_COMPLETED" in types


@patch("app.analytics.timeline.sos_service.list_sos")
@patch("app.analytics.timeline.alerts_service.list_alerts")
@patch("app.analytics.timeline.intelligence_events.list_events")
@patch("app.analytics.timeline.route_service.get_route_by_trip")
def test_cancelled_trip_reports_cancelled_not_completed(mock_route, mock_events, mock_alerts, mock_sos):
    mock_route.return_value = None
    mock_events.return_value = []
    mock_alerts.return_value = []
    mock_sos.return_value = []

    trip = make_trip(status=TripStatus.CANCELLED, started_at=None, ended_at=None)
    events = build_timeline(None, trip)
    types = [e.type for e in events]

    assert "TRIP_CANCELLED" in types
    assert "TRIP_COMPLETED" not in types


@patch("app.analytics.timeline.sos_service.list_sos")
@patch("app.analytics.timeline.alerts_service.list_alerts")
@patch("app.analytics.timeline.intelligence_events.list_events")
@patch("app.analytics.timeline.route_service.get_route_by_trip")
def test_anomaly_intelligence_events_included_movement_noise_excluded(mock_route, mock_events, mock_alerts, mock_sos):
    mock_route.return_value = None
    mock_events.return_value = [
        make_event(IntelligenceEventType.ROUTE_DEVIATION, T0 + timedelta(minutes=5)),
        make_event(IntelligenceEventType.MOVING, T0 + timedelta(minutes=6)),
        make_event(IntelligenceEventType.STOPPED, T0 + timedelta(minutes=7)),
    ]
    mock_alerts.return_value = []
    mock_sos.return_value = []

    trip = make_trip()
    events = build_timeline(None, trip)
    types = [e.type for e in events]

    assert "ROUTE_DEVIATION" in types
    assert "MOVING" not in types
    assert "STOPPED" not in types


@patch("app.analytics.timeline.sos_service.list_sos")
@patch("app.analytics.timeline.alerts_service.list_alerts")
@patch("app.analytics.timeline.intelligence_events.list_events")
@patch("app.analytics.timeline.route_service.get_route_by_trip")
def test_alert_and_sos_created_and_resolved_are_distinct_entries(mock_route, mock_events, mock_alerts, mock_sos):
    mock_route.return_value = None
    mock_events.return_value = []
    mock_alerts.return_value = [make_alert(T0 + timedelta(minutes=1), resolved_at=T0 + timedelta(minutes=5))]
    mock_sos.return_value = [make_sos(T0 + timedelta(minutes=2), resolved_at=T0 + timedelta(minutes=6))]

    trip = make_trip()
    events = build_timeline(None, trip)
    types = [e.type for e in events]

    assert types.count("ALERT_CREATED") == 1
    assert types.count("ALERT_RESOLVED") == 1
    assert types.count("SOS") == 1
    assert types.count("SOS_RESOLVED") == 1


@patch("app.analytics.timeline.sos_service.list_sos")
@patch("app.analytics.timeline.alerts_service.list_alerts")
@patch("app.analytics.timeline.intelligence_events.list_events")
@patch("app.analytics.timeline.route_service.get_route_by_trip")
def test_route_created_and_activated_included_when_route_exists(mock_route, mock_events, mock_alerts, mock_sos):
    mock_route.return_value = SimpleNamespace(
        id=uuid.uuid4(), created_at=T0 - timedelta(minutes=5), name="Test route", status=RouteStatus.ACTIVE
    )
    mock_events.return_value = []
    mock_alerts.return_value = []
    mock_sos.return_value = []

    trip = make_trip()
    events = build_timeline(None, trip)
    types = [e.type for e in events]

    assert "ROUTE_CREATED" in types
    assert "ROUTE_ACTIVATED" in types


@patch("app.analytics.timeline.sos_service.list_sos")
@patch("app.analytics.timeline.alerts_service.list_alerts")
@patch("app.analytics.timeline.intelligence_events.list_events")
@patch("app.analytics.timeline.route_service.get_route_by_trip")
def test_no_route_no_route_events(mock_route, mock_events, mock_alerts, mock_sos):
    mock_route.return_value = None
    mock_events.return_value = []
    mock_alerts.return_value = []
    mock_sos.return_value = []

    trip = make_trip()
    events = build_timeline(None, trip)
    types = [e.type for e in events]

    assert "ROUTE_CREATED" not in types
    assert "ROUTE_ACTIVATED" not in types
