"""app/analytics/trip_analytics.py — trip-level headline composition,
patched-service-function pattern (no live database)."""

import uuid
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import patch

from app.analytics.trip_analytics import compute_trip_analytics
from app.models.enums import TripStatus
from app.schemas.analytics import RouteAnalytics

TRIP_ID = uuid.uuid4()
GROUP_ID = uuid.uuid4()
T0 = datetime(2026, 8, 30, 10, 0, tzinfo=timezone.utc)


def make_trip(**overrides):
    trip = SimpleNamespace(
        id=TRIP_ID, group_id=GROUP_ID, status=TripStatus.COMPLETED,
        started_at=T0, ended_at=T0 + timedelta(hours=2),
    )
    for k, v in overrides.items():
        setattr(trip, k, v)
    return trip


def _patches():
    return [
        patch("app.analytics.trip_analytics.queries.list_active_group_members", return_value=[{"user_id": uuid.uuid4()}] * 4),
        patch("app.analytics.trip_analytics.queries.get_group_leader_id", return_value=None),
        patch("app.analytics.trip_analytics.queries.fetch_location_points", return_value={}),
        patch("app.analytics.trip_analytics.queries.compute_distances_by_user", return_value={}),
        patch("app.analytics.trip_analytics.queries.pick_representative_value", return_value=None),
        patch(
            "app.analytics.trip_analytics.build_route_analytics",
            return_value=RouteAnalytics(route_available=False, route_deviations=0, resolved_deviations=0, active_deviations=0),
        ),
        patch("app.analytics.trip_analytics.alerts_service.list_alerts", return_value=[]),
        patch("app.analytics.trip_analytics.sos_service.list_sos", return_value=[]),
        patch("app.analytics.trip_analytics.intelligence_events.list_events", return_value=[]),
    ]


def _apply(patches):
    mocks = [p.start() for p in patches]
    return mocks


def test_no_gps_no_route_reports_null_not_zero():
    patches = _patches()
    for p in patches:
        p.start()
    try:
        trip = make_trip()
        result = compute_trip_analytics(None, trip)
    finally:
        for p in patches:
            p.stop()

    assert result.distance_traveled_meters is None
    assert result.route_available is False
    assert result.planned_distance_meters is None
    assert result.member_count == 4
    assert result.alerts_count == 0  # genuinely zero, not null


def test_duration_computed_for_completed_trip():
    patches = _patches()
    for p in patches:
        p.start()
    try:
        trip = make_trip(status=TripStatus.COMPLETED, started_at=T0, ended_at=T0 + timedelta(hours=2))
        result = compute_trip_analytics(None, trip)
    finally:
        for p in patches:
            p.stop()

    assert result.duration_seconds == 7200


@patch("app.analytics.trip_analytics.intelligence_events.list_events")
@patch("app.analytics.trip_analytics.sos_service.list_sos")
@patch("app.analytics.trip_analytics.alerts_service.list_alerts")
@patch("app.analytics.trip_analytics.build_route_analytics")
@patch("app.analytics.trip_analytics.queries.pick_representative_value")
@patch("app.analytics.trip_analytics.queries.compute_distances_by_user")
@patch("app.analytics.trip_analytics.queries.fetch_location_points")
@patch("app.analytics.trip_analytics.queries.get_group_leader_id")
@patch("app.analytics.trip_analytics.queries.list_active_group_members")
def test_route_available_and_completion_carried_from_route_analytics(
    mock_members, mock_leader, mock_points, mock_distances, mock_repr, mock_route, mock_alerts, mock_sos, mock_events
):
    mock_members.return_value = []
    mock_leader.return_value = None
    mock_points.return_value = {}
    mock_distances.return_value = {}
    mock_repr.return_value = None
    mock_route.return_value = RouteAnalytics(
        route_available=True, planned_distance_meters=60000.0, traveled_distance_meters=58300.0,
        completion_percent=97.2, route_deviations=2, resolved_deviations=2, active_deviations=0,
    )
    mock_alerts.return_value = []
    mock_sos.return_value = []
    mock_events.return_value = []

    trip = make_trip()
    result = compute_trip_analytics(None, trip)

    assert result.route_available is True
    assert result.planned_distance_meters == 60000.0
    assert result.route_completion_percent == 97.2


@patch("app.analytics.trip_analytics.intelligence_events.list_events")
@patch("app.analytics.trip_analytics.sos_service.list_sos")
@patch("app.analytics.trip_analytics.alerts_service.list_alerts")
@patch("app.analytics.trip_analytics.build_route_analytics")
@patch("app.analytics.trip_analytics.queries.pick_representative_value")
@patch("app.analytics.trip_analytics.queries.compute_distances_by_user")
@patch("app.analytics.trip_analytics.queries.fetch_location_points")
@patch("app.analytics.trip_analytics.queries.get_group_leader_id")
@patch("app.analytics.trip_analytics.queries.list_active_group_members")
def test_source_field_reflects_caller(
    mock_members, mock_leader, mock_points, mock_distances, mock_repr, mock_route, mock_alerts, mock_sos, mock_events
):
    mock_members.return_value = []
    mock_leader.return_value = None
    mock_points.return_value = {}
    mock_distances.return_value = {}
    mock_repr.return_value = None
    mock_route.return_value = RouteAnalytics(route_available=False, route_deviations=0, resolved_deviations=0, active_deviations=0)
    mock_alerts.return_value = []
    mock_sos.return_value = []
    mock_events.return_value = []

    trip = make_trip()
    result = compute_trip_analytics(None, trip, source="snapshot")

    assert result.source == "snapshot"
