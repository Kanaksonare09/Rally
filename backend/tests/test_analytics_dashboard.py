"""
app/analytics/dashboard.py — live vs historical dashboard composition.
Every collaborator (intelligence engine, route service, alert/SOS
services, analytics queries, risk, notifications) is patched at the point
dashboard.py imports it — same patched-service-function pattern as the
rest of this codebase's API-level tests, since dashboard.py is pure
composition, not its own business logic. Risk and notifications are
patched at the module level (autouse) in every test here since they're
DB-only and every test in this file passes db=None — see
test_risk_service.py / test_notification_service.py for their own
dedicated unit tests.
"""

import uuid
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from app.analytics.dashboard import build_dashboard
from app.models.enums import RouteStatus, TripStatus
from app.schemas.risk import RiskScore

TRIP_ID = uuid.uuid4()
GROUP_ID = uuid.uuid4()
USER_A = str(uuid.uuid4())
USER_B = str(uuid.uuid4())
VIEWER_ID = uuid.UUID(USER_A)


@pytest.fixture(autouse=True)
def _stub_risk_and_notifications():
    with patch("app.analytics.dashboard.calculate_trip_risk", return_value=RiskScore(score=0, level="LOW", factors=[])), \
         patch("app.analytics.dashboard.notification_service.get_unread_count", return_value=0):
        yield


def make_trip(**overrides):
    trip = SimpleNamespace(
        id=TRIP_ID, group_id=GROUP_ID, status=TripStatus.ACTIVE, started_at=datetime.now(timezone.utc),
        destination_name="Indore Ride",
    )
    for k, v in overrides.items():
        setattr(trip, k, v)
    return trip


def make_computed_member(user_id, movement_state="MOVING", presence="ONLINE", distance_from_group_center_meters=50.0, speed=5.0):
    return SimpleNamespace(
        user_id=user_id, name="Test", role="MEMBER", movement_state=movement_state, presence=presence,
        distance_from_group_center_meters=distance_from_group_center_meters, latitude=22.7, longitude=75.8, speed=speed,
    )


def make_computed_state(members):
    return SimpleNamespace(members=members)


def make_route(status=RouteStatus.ACTIVE):
    return SimpleNamespace(
        id=uuid.uuid4(), trip_id=TRIP_ID, distance_meters=60000.0, estimated_duration_seconds=None, status=status
    )


class _FakeMatch(SimpleNamespace):
    pass


def make_route_progress_member(user_id, fraction=0.4, remaining=36000.0, distance_from_route=5.0, eta_seconds=3600.0):
    match = _FakeMatch(route_fraction=fraction, distance_remaining_meters=remaining, distance_from_route_meters=distance_from_route)
    eta = SimpleNamespace(eta_seconds=eta_seconds, eta_available=True, source="route_baseline")
    return SimpleNamespace(user_id=user_id, name="Test", role="MEMBER", presence="ONLINE", match=match, route_state="ON_ROUTE", eta=eta)


@patch("app.analytics.dashboard.sos_service.list_active_sos")
@patch("app.analytics.dashboard.alerts_service.list_active_alerts")
@patch("app.analytics.dashboard.route_service.get_live_route_progress", new_callable=AsyncMock)
@patch("app.analytics.dashboard.route_service.get_route_by_trip")
@patch("app.analytics.dashboard.intelligence_engine.compute_current_state", new_callable=AsyncMock)
@patch("app.analytics.dashboard.queries.get_group_leader_id")
async def test_active_trip_uses_live_mode(mock_leader, mock_compute, mock_route, mock_progress, mock_alerts, mock_sos):
    mock_leader.return_value = uuid.UUID(USER_A)
    mock_compute.return_value = make_computed_state(
        [make_computed_member(USER_A, "MOVING", "ONLINE"), make_computed_member(USER_B, "STOPPED", "ONLINE")]
    )
    mock_route.return_value = make_route(status=RouteStatus.ACTIVE)
    mock_progress.return_value = (
        [make_route_progress_member(USER_A, fraction=0.5), make_route_progress_member(USER_B, fraction=0.3)],
        0.4,
        False,
    )
    mock_alerts.return_value = []
    mock_sos.return_value = []

    result = await build_dashboard(db=None, redis=object(), trip=make_trip(status=TripStatus.ACTIVE), viewer_user_id=VIEWER_ID)

    assert result.mode == "live"
    assert result.group.member_count == 2
    assert result.group.online_count == 2
    assert result.group.moving_count == 1
    assert result.group.stopped_count == 1
    assert result.route.route_available is True
    assert result.route.progress_percent == 50.0  # leader (USER_A)'s own fraction
    assert len(result.members) == 2
    assert result.risk.level == "LOW"
    assert result.notifications.unread_count == 0
    assert result.eta.eta_available is True
    assert result.eta.group_eta_available is True


@patch("app.analytics.dashboard.sos_service.list_active_sos")
@patch("app.analytics.dashboard.alerts_service.list_active_alerts")
@patch("app.analytics.dashboard.intelligence_engine.compute_current_state", new_callable=AsyncMock)
@patch("app.analytics.dashboard.route_service.get_route_by_trip")
@patch("app.analytics.dashboard.queries.get_group_leader_id")
@patch("app.analytics.dashboard.queries.list_active_group_members")
async def test_active_trip_with_redis_down_degrades_gracefully(
    mock_members, mock_leader, mock_route, mock_compute, mock_alerts, mock_sos
):
    mock_members.return_value = [{"user_id": uuid.UUID(USER_A), "name": "A", "role": "MEMBER", "joined_at": None}]
    mock_leader.return_value = None
    mock_route.return_value = None
    mock_alerts.return_value = []
    mock_sos.return_value = []

    result = await build_dashboard(db=None, redis=None, trip=make_trip(status=TripStatus.ACTIVE), viewer_user_id=VIEWER_ID)

    assert result.mode == "live"
    assert result.group.online_count is None
    assert result.group.moving_count is None
    assert result.group.stopped_count is None
    assert result.weather.weather_available is False
    assert result.eta.eta_available is False
    mock_compute.assert_not_called()


@patch("app.analytics.dashboard.sos_service.list_active_sos")
@patch("app.analytics.dashboard.alerts_service.list_active_alerts")
@patch("app.analytics.dashboard.route_analytics.match_last_point")
@patch("app.analytics.dashboard.route_analytics.compute_route_completion")
@patch("app.analytics.dashboard.route_service.get_route_by_trip")
@patch("app.analytics.dashboard.queries.fetch_movement_intervals_by_user")
@patch("app.analytics.dashboard.queries.fetch_location_points")
@patch("app.analytics.dashboard.queries.get_group_leader_id")
@patch("app.analytics.dashboard.queries.list_active_group_members")
async def test_completed_trip_uses_historical_mode_and_no_eta(
    mock_members, mock_leader, mock_points, mock_movement, mock_route, mock_completion, mock_match, mock_alerts, mock_sos
):
    mock_members.return_value = [{"user_id": uuid.UUID(USER_A), "name": "A", "role": "LEADER", "joined_at": None}]
    mock_leader.return_value = uuid.UUID(USER_A)
    mock_points.return_value = {}
    mock_movement.return_value = {}
    mock_route.return_value = make_route(status=RouteStatus.COMPLETED)
    mock_completion.return_value = (97.2, 1600.0, True)
    mock_match.return_value = None
    mock_alerts.return_value = []
    mock_sos.return_value = []

    result = await build_dashboard(db=None, redis=None, trip=make_trip(status=TripStatus.COMPLETED), viewer_user_id=VIEWER_ID)

    assert result.mode == "historical"
    assert result.route.eta_seconds is None
    assert result.route.progress_percent == 97.2
    assert result.group.online_count is None
    assert result.eta.eta_available is False
    assert result.weather.weather_available is False


@patch("app.analytics.dashboard.sos_service.list_active_sos")
@patch("app.analytics.dashboard.alerts_service.list_active_alerts")
@patch("app.analytics.dashboard.route_service.get_route_by_trip")
@patch("app.analytics.dashboard.queries.fetch_movement_intervals_by_user")
@patch("app.analytics.dashboard.queries.fetch_location_points")
@patch("app.analytics.dashboard.queries.get_group_leader_id")
@patch("app.analytics.dashboard.queries.list_active_group_members")
async def test_completed_trip_no_route_reports_unavailable(
    mock_members, mock_leader, mock_points, mock_movement, mock_route, mock_alerts, mock_sos
):
    mock_members.return_value = []
    mock_leader.return_value = None
    mock_points.return_value = {}
    mock_movement.return_value = {}
    mock_route.return_value = None
    mock_alerts.return_value = []
    mock_sos.return_value = []

    result = await build_dashboard(db=None, redis=None, trip=make_trip(status=TripStatus.CANCELLED), viewer_user_id=VIEWER_ID)

    assert result.mode == "historical"
    assert result.route.route_available is False
    assert result.route.distance_meters is None


@patch("app.analytics.dashboard.sos_service.list_active_sos")
@patch("app.analytics.dashboard.alerts_service.list_active_alerts")
async def test_active_alerts_and_sos_counted_in_safety(mock_alerts, mock_sos):
    from types import SimpleNamespace as SN

    with patch("app.analytics.dashboard.queries.list_active_group_members", return_value=[]), \
         patch("app.analytics.dashboard.queries.get_group_leader_id", return_value=None), \
         patch("app.analytics.dashboard.queries.fetch_location_points", return_value={}), \
         patch("app.analytics.dashboard.queries.fetch_movement_intervals_by_user", return_value={}), \
         patch("app.analytics.dashboard.route_service.get_route_by_trip", return_value=None):
        mock_alerts.return_value = [SN(severity=SN(value="CRITICAL")), SN(severity=SN(value="WARNING"))]
        mock_sos.return_value = [SN()]

        result = await build_dashboard(db=None, redis=None, trip=make_trip(status=TripStatus.COMPLETED), viewer_user_id=VIEWER_ID)

    assert result.safety.active_alerts == 2
    assert result.safety.critical_alerts == 1
    assert result.safety.active_sos == 1


# ---- Phase 12 additions: risk / eta / weather / notifications -----------


@patch("app.analytics.dashboard.sos_service.list_active_sos")
@patch("app.analytics.dashboard.alerts_service.list_active_alerts")
@patch("app.analytics.dashboard.route_service.get_live_route_progress", new_callable=AsyncMock)
@patch("app.analytics.dashboard.route_service.get_route_by_trip")
@patch("app.analytics.dashboard.intelligence_engine.compute_current_state", new_callable=AsyncMock)
@patch("app.analytics.dashboard.queries.get_group_leader_id")
async def test_dashboard_notifications_scoped_to_the_viewer(mock_leader, mock_compute, mock_route, mock_progress, mock_alerts, mock_sos):
    mock_leader.return_value = uuid.UUID(USER_A)
    mock_compute.return_value = make_computed_state([make_computed_member(USER_A)])
    mock_route.return_value = None
    mock_progress.return_value = ([], None, False)
    mock_alerts.return_value = []
    mock_sos.return_value = []

    with patch("app.analytics.dashboard.notification_service.get_unread_count", return_value=3) as mock_unread:
        result = await build_dashboard(db="fake-db", redis=object(), trip=make_trip(status=TripStatus.ACTIVE), viewer_user_id=VIEWER_ID)

    mock_unread.assert_called_once_with("fake-db", VIEWER_ID)
    assert result.notifications.unread_count == 3


@patch("app.analytics.dashboard.sos_service.list_active_sos")
@patch("app.analytics.dashboard.alerts_service.list_active_alerts")
@patch("app.analytics.dashboard.route_service.get_live_route_progress", new_callable=AsyncMock)
@patch("app.analytics.dashboard.route_service.get_route_by_trip")
@patch("app.analytics.dashboard.intelligence_engine.compute_current_state", new_callable=AsyncMock)
@patch("app.analytics.dashboard.queries.get_group_leader_id")
async def test_dashboard_weather_uses_leader_location_when_available(mock_leader, mock_compute, mock_route, mock_progress, mock_alerts, mock_sos):
    from app.weather.service import WeatherInfo

    mock_leader.return_value = uuid.UUID(USER_A)
    mock_compute.return_value = make_computed_state([make_computed_member(USER_A), make_computed_member(USER_B)])
    mock_route.return_value = None
    mock_progress.return_value = ([], None, False)
    mock_alerts.return_value = []
    mock_sos.return_value = []

    with patch(
        "app.analytics.dashboard.WeatherService.get_weather", new_callable=AsyncMock,
        return_value=WeatherInfo(weather_available=True, temperature_celsius=30.0, condition="CLEAR"),
    ) as mock_weather:
        result = await build_dashboard(db=None, redis=object(), trip=make_trip(status=TripStatus.ACTIVE), viewer_user_id=VIEWER_ID)

    mock_weather.assert_called_once()
    assert result.weather.weather_available is True
    assert result.weather.temperature_celsius == 30.0


async def test_dashboard_risk_reflected_in_response():
    from app.schemas.risk import RiskFactor

    with patch("app.analytics.dashboard.queries.list_active_group_members", return_value=[]), \
         patch("app.analytics.dashboard.queries.get_group_leader_id", return_value=None), \
         patch("app.analytics.dashboard.queries.fetch_location_points", return_value={}), \
         patch("app.analytics.dashboard.queries.fetch_movement_intervals_by_user", return_value={}), \
         patch("app.analytics.dashboard.route_service.get_route_by_trip", return_value=None), \
         patch("app.analytics.dashboard.alerts_service.list_active_alerts", return_value=[]), \
         patch("app.analytics.dashboard.sos_service.list_active_sos", return_value=[]), \
         patch(
             "app.analytics.dashboard.calculate_trip_risk",
             return_value=RiskScore(score=67, level="HIGH", factors=[RiskFactor(type="ACTIVE_SOS", impact=50, description="x")]),
         ):
        result = await build_dashboard(db=None, redis=None, trip=make_trip(status=TripStatus.COMPLETED), viewer_user_id=VIEWER_ID)

    assert result.risk.score == 67
    assert result.risk.level == "HIGH"
