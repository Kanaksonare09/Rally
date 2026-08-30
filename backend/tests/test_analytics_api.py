"""
Endpoint-level tests for app/api/analytics.py: authentication and trip-
membership authorization on every Phase 10 analytics endpoint, plus the
snapshot-vs-live serving decision on GET /trips/{trip_id}/analytics —
same patched-service-function pattern as test_trips_api.py/test_route_api.py
(no live database in this environment).
"""

import uuid
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient

from app.core.config import settings
from app.core.database import get_db
from app.dependencies.trip import require_trip_member
from app.main import app
from app.models.enums import TripStatus
from app.schemas.analytics import (
    DashboardEta,
    DashboardGroup,
    DashboardMember,
    DashboardNotifications,
    DashboardResponse,
    DashboardRisk,
    DashboardRoute,
    DashboardSafety,
    DashboardTrip,
    DashboardWeather,
    MemberAnalyticsResponse,
    RouteAnalytics,
    SafetyAnalytics,
    TripAnalytics,
    TripTimeline,
)

# Phase 12 additions to DashboardResponse — a fixed, minimal set of
# defaults for the tests below, which only care about the pre-Phase-12
# fields they assert on.
_MINIMAL_DASHBOARD_EXTRAS = dict(
    risk=DashboardRisk(score=0, level="LOW"),
    eta=DashboardEta(eta_available=False, eta_seconds=None),
    weather=DashboardWeather(weather_available=False),
    notifications=DashboardNotifications(unread_count=0),
)

client = TestClient(app)
API = settings.API_V1_STR
TRIP_ID = uuid.uuid4()

ANALYTICS_ENDPOINTS = [
    "/trips/{trip_id}/analytics",
    "/trips/{trip_id}/analytics/members",
    "/trips/{trip_id}/analytics/route",
    "/trips/{trip_id}/analytics/safety",
    "/trips/{trip_id}/timeline",
    "/trips/{trip_id}/dashboard",
    "/trips/{trip_id}/replay",
    "/trips/{trip_id}/risk",
    "/trips/{trip_id}/insights",
]


def make_mock_trip(**overrides) -> SimpleNamespace:
    trip = SimpleNamespace(
        id=TRIP_ID, group_id=uuid.uuid4(), status=TripStatus.COMPLETED, destination_name="Test Trip",
        started_at=None, ended_at=None,
    )
    for k, v in overrides.items():
        setattr(trip, k, v)
    return trip


def _fixed_analytics(**overrides) -> TripAnalytics:
    defaults = dict(
        trip_id=TRIP_ID, status="COMPLETED", started_at=None, ended_at=None, duration_seconds=None,
        member_count=0, distance_traveled_meters=None, route_available=False, planned_distance_meters=None,
        route_completion_percent=None, alerts_count=0, critical_alerts_count=0, sos_count=0,
        route_deviations=0, source="live",
    )
    defaults.update(overrides)
    return TripAnalytics(**defaults)


# ---- unauthenticated ---------------------------------------------------


def test_unauthenticated_cannot_access_any_analytics_endpoint():
    for path in ANALYTICS_ENDPOINTS:
        response = client.get(f"{API}{path.format(trip_id=TRIP_ID)}")
        assert response.status_code == 401, path


# ---- non-member -----------------------------------------------------------


def test_non_member_cannot_access_any_analytics_endpoint():
    from app.dependencies.trip import get_trip_membership

    def _raise_not_found():
        from app.core.errors import AppHTTPException

        raise AppHTTPException(status_code=404, code="TRIP_NOT_FOUND", detail="Trip not found.")

    app.dependency_overrides[get_trip_membership] = _raise_not_found
    from tests.conftest import DEFAULT_TEST_USER_ID, make_token

    token = make_token(sub=DEFAULT_TEST_USER_ID)
    try:
        for path in ANALYTICS_ENDPOINTS:
            response = client.get(f"{API}{path.format(trip_id=TRIP_ID)}", headers={"Authorization": f"Bearer {token}"})
            assert response.status_code == 404, path
    finally:
        app.dependency_overrides.pop(get_trip_membership, None)


# ---- trip analytics: snapshot vs live --------------------------------------


@patch("app.api.analytics.get_snapshot")
def test_completed_trip_serves_existing_snapshot(mock_get_snapshot):
    trip = make_mock_trip(status=TripStatus.COMPLETED)
    app.dependency_overrides[require_trip_member] = lambda: trip
    app.dependency_overrides[get_db] = lambda: None

    mock_get_snapshot.return_value = SimpleNamespace(
        duration_seconds=7200, member_count=4, distance_traveled_meters=58300.0,
        planned_distance_meters=60000.0, completion_percent=97.2,
        alerts_count=3, critical_alerts_count=0, sos_count=0, route_deviations=2,
    )
    from tests.conftest import DEFAULT_TEST_USER_ID, make_token

    token = make_token(sub=DEFAULT_TEST_USER_ID)
    try:
        response = client.get(f"{API}/trips/{TRIP_ID}/analytics", headers={"Authorization": f"Bearer {token}"})
    finally:
        app.dependency_overrides.pop(require_trip_member, None)
        app.dependency_overrides.pop(get_db, None)

    assert response.status_code == 200
    body = response.json()
    assert body["source"] == "snapshot"
    assert body["distance_traveled_meters"] == 58300.0


@patch("app.api.analytics.trip_analytics_module.compute_trip_analytics")
@patch("app.api.analytics.get_snapshot")
def test_completed_trip_without_snapshot_computes_live(mock_get_snapshot, mock_compute):
    trip = make_mock_trip(status=TripStatus.COMPLETED)
    app.dependency_overrides[require_trip_member] = lambda: trip
    app.dependency_overrides[get_db] = lambda: None
    mock_get_snapshot.return_value = None
    mock_compute.return_value = _fixed_analytics(source="live")

    from tests.conftest import DEFAULT_TEST_USER_ID, make_token

    token = make_token(sub=DEFAULT_TEST_USER_ID)
    try:
        response = client.get(f"{API}/trips/{TRIP_ID}/analytics", headers={"Authorization": f"Bearer {token}"})
    finally:
        app.dependency_overrides.pop(require_trip_member, None)
        app.dependency_overrides.pop(get_db, None)

    assert response.status_code == 200
    assert response.json()["source"] == "live"


@patch("app.api.analytics.trip_analytics_module.compute_trip_analytics")
def test_active_trip_always_computes_live_never_checks_snapshot(mock_compute):
    trip = make_mock_trip(status=TripStatus.ACTIVE)
    app.dependency_overrides[require_trip_member] = lambda: trip
    app.dependency_overrides[get_db] = lambda: None
    mock_compute.return_value = _fixed_analytics(status="ACTIVE", source="live")

    from tests.conftest import DEFAULT_TEST_USER_ID, make_token

    token = make_token(sub=DEFAULT_TEST_USER_ID)
    try:
        with patch("app.api.analytics.get_snapshot") as mock_snapshot:
            response = client.get(f"{API}/trips/{TRIP_ID}/analytics", headers={"Authorization": f"Bearer {token}"})
            mock_snapshot.assert_not_called()
    finally:
        app.dependency_overrides.pop(require_trip_member, None)
        app.dependency_overrides.pop(get_db, None)

    assert response.status_code == 200


# ---- zero vs null over HTTP -------------------------------------------


@patch("app.api.analytics.route_analytics_module.build_route_analytics")
def test_no_route_returns_null_fields_not_zero(mock_route):
    trip = make_mock_trip()
    app.dependency_overrides[require_trip_member] = lambda: trip
    app.dependency_overrides[get_db] = lambda: None
    mock_route.return_value = RouteAnalytics(
        route_available=False, route_deviations=0, resolved_deviations=0, active_deviations=0
    )

    from tests.conftest import DEFAULT_TEST_USER_ID, make_token

    token = make_token(sub=DEFAULT_TEST_USER_ID)
    try:
        response = client.get(f"{API}/trips/{TRIP_ID}/analytics/route", headers={"Authorization": f"Bearer {token}"})
    finally:
        app.dependency_overrides.pop(require_trip_member, None)
        app.dependency_overrides.pop(get_db, None)

    assert response.status_code == 200
    body = response.json()
    assert body["route_available"] is False
    assert body["planned_distance_meters"] is None
    assert body["route_deviations"] == 0  # a real zero, not omitted


# ---- dashboard: live vs historical ------------------------------------


@patch("app.api.analytics.build_dashboard", new_callable=AsyncMock)
def test_dashboard_active_trip_tries_redis(mock_dashboard):
    trip = make_mock_trip(status=TripStatus.ACTIVE)
    app.dependency_overrides[require_trip_member] = lambda: trip
    app.dependency_overrides[get_db] = lambda: None
    mock_dashboard.return_value = DashboardResponse(
        mode="live",
        trip=DashboardTrip(id=TRIP_ID, name="Test", status="ACTIVE", started_at=None),
        route=DashboardRoute(route_available=False),
        group=DashboardGroup(member_count=1),
        safety=DashboardSafety(active_alerts=0, critical_alerts=0, active_sos=0),
        members=[],
        **_MINIMAL_DASHBOARD_EXTRAS,
    )

    from tests.conftest import DEFAULT_TEST_USER_ID, make_token

    token = make_token(sub=DEFAULT_TEST_USER_ID)
    try:
        response = client.get(f"{API}/trips/{TRIP_ID}/dashboard", headers={"Authorization": f"Bearer {token}"})
    finally:
        app.dependency_overrides.pop(require_trip_member, None)
        app.dependency_overrides.pop(get_db, None)

    assert response.status_code == 200
    assert response.json()["mode"] == "live"


@patch("app.api.analytics.build_dashboard", new_callable=AsyncMock)
def test_dashboard_completed_trip_never_calls_get_redis(mock_dashboard):
    trip = make_mock_trip(status=TripStatus.COMPLETED)
    app.dependency_overrides[require_trip_member] = lambda: trip
    app.dependency_overrides[get_db] = lambda: None
    mock_dashboard.return_value = DashboardResponse(
        mode="historical",
        trip=DashboardTrip(id=TRIP_ID, name="Test", status="COMPLETED", started_at=None),
        route=DashboardRoute(route_available=False),
        group=DashboardGroup(member_count=1),
        safety=DashboardSafety(active_alerts=0, critical_alerts=0, active_sos=0),
        members=[],
        **_MINIMAL_DASHBOARD_EXTRAS,
    )

    from tests.conftest import DEFAULT_TEST_USER_ID, make_token

    token = make_token(sub=DEFAULT_TEST_USER_ID)
    try:
        with patch("app.api.analytics.get_redis") as mock_get_redis:
            response = client.get(f"{API}/trips/{TRIP_ID}/dashboard", headers={"Authorization": f"Bearer {token}"})
            mock_get_redis.assert_not_called()
    finally:
        app.dependency_overrides.pop(require_trip_member, None)
        app.dependency_overrides.pop(get_db, None)

    assert response.status_code == 200
    assert response.json()["mode"] == "historical"


# ---- Phase 12: replay / risk / insights ------------------------------


@patch("app.api.analytics.replay_module.build_replay")
def test_replay_endpoint_clamps_interval_seconds(mock_build):
    from app.schemas.analytics import TripReplay

    trip = make_mock_trip(status=TripStatus.COMPLETED)
    app.dependency_overrides[require_trip_member] = lambda: trip
    app.dependency_overrides[get_db] = lambda: None
    mock_build.return_value = TripReplay(
        trip_id=TRIP_ID, duration_seconds=None, total_distance_meters=None, interval_seconds=5, timeline=[], events=[]
    )
    from tests.conftest import DEFAULT_TEST_USER_ID, make_token

    token = make_token(sub=DEFAULT_TEST_USER_ID)
    try:
        # Requesting a wildly-out-of-range interval must be rejected by
        # the endpoint's own Query() bounds, never silently clamped by
        # the router (build_replay does its own internal clamping too —
        # see test_replay.py — but the HTTP contract itself still
        # validates input).
        response = client.get(
            f"{API}/trips/{TRIP_ID}/replay?interval_seconds=999999999", headers={"Authorization": f"Bearer {token}"}
        )
        assert response.status_code == 422

        response = client.get(f"{API}/trips/{TRIP_ID}/replay", headers={"Authorization": f"Bearer {token}"})
    finally:
        app.dependency_overrides.pop(require_trip_member, None)
        app.dependency_overrides.pop(get_db, None)

    assert response.status_code == 200
    mock_build.assert_called_once()


@patch("app.api.analytics.calculate_trip_risk")
def test_risk_endpoint_returns_service_result(mock_risk):
    from app.schemas.risk import RiskFactor, RiskScore

    trip = make_mock_trip(status=TripStatus.ACTIVE)
    app.dependency_overrides[require_trip_member] = lambda: trip
    app.dependency_overrides[get_db] = lambda: None
    mock_risk.return_value = RiskScore(score=67, level="HIGH", factors=[RiskFactor(type="ACTIVE_SOS", impact=50, description="x")])
    from tests.conftest import DEFAULT_TEST_USER_ID, make_token

    token = make_token(sub=DEFAULT_TEST_USER_ID)
    try:
        response = client.get(f"{API}/trips/{TRIP_ID}/risk", headers={"Authorization": f"Bearer {token}"})
    finally:
        app.dependency_overrides.pop(require_trip_member, None)
        app.dependency_overrides.pop(get_db, None)

    assert response.status_code == 200
    body = response.json()
    assert body["score"] == 67
    assert body["level"] == "HIGH"


@patch("app.api.analytics.insights_module.build_trip_insights")
def test_insights_endpoint_returns_service_result(mock_insights):
    from app.schemas.analytics import TripInsights, TripInsightsStatistics

    trip = make_mock_trip(status=TripStatus.COMPLETED)
    app.dependency_overrides[require_trip_member] = lambda: trip
    app.dependency_overrides[get_db] = lambda: None
    mock_insights.return_value = TripInsights(
        trip_id=TRIP_ID, highlights=["All members finished the trip safely."],
        statistics=TripInsightsStatistics(alerts=0, sos=0, route_deviations=0, member_count=4, active_member_count=4),
    )
    from tests.conftest import DEFAULT_TEST_USER_ID, make_token

    token = make_token(sub=DEFAULT_TEST_USER_ID)
    try:
        response = client.get(f"{API}/trips/{TRIP_ID}/insights", headers={"Authorization": f"Bearer {token}"})
    finally:
        app.dependency_overrides.pop(require_trip_member, None)
        app.dependency_overrides.pop(get_db, None)

    assert response.status_code == 200
    assert "safely" in response.json()["highlights"][0]


# ---- regression --------------------------------------------------------


def test_health_endpoint_still_works():
    response = client.get(f"{API}/health")
    assert response.status_code == 200
