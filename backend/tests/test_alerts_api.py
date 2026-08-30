"""
Endpoint-level tests for the alerts API: authorization (same
require_trip_member / require_alert_member pattern as trips/intelligence)
and the security guarantees explicitly required by this phase (no
cross-group access to read/acknowledge/resolve). Service calls mocked —
no live database/Redis required.
"""

import uuid
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.core.config import settings
from app.core.database import get_db
from app.dependencies.alert import require_alert_member
from app.dependencies.trip import require_trip_member
from app.main import app
from app.models.enums import AlertSeverity, AlertStatus, AlertType
from tests.conftest import DEFAULT_TEST_USER_ID, make_token

client = TestClient(app)
API = settings.API_V1_STR
TRIP_ID = uuid.uuid4()
ALERT_ID = uuid.uuid4()
URL_LIST = f"{API}/trips/{TRIP_ID}/alerts"
URL_ACTIVE = f"{API}/trips/{TRIP_ID}/alerts/active"
URL_ONE = f"{API}/alerts/{ALERT_ID}"


def make_mock_trip():
    trip = MagicMock()
    trip.id = TRIP_ID
    trip.group_id = uuid.uuid4()
    return trip


def make_mock_alert(**overrides):
    alert = MagicMock()
    alert.id = ALERT_ID
    alert.trip_id = TRIP_ID
    alert.event_id = uuid.uuid4()
    alert.alert_type = AlertType.FALLING_BEHIND
    alert.severity = AlertSeverity.WARNING
    alert.status = AlertStatus.ACTIVE
    alert.title = "Member falling behind"
    alert.message = "A group member is falling behind."
    alert.user_id = uuid.uuid4()
    alert.related_user_id = None
    alert.alert_metadata = {"distance_meters": 650}
    alert.created_at = datetime.now(timezone.utc)
    alert.acknowledged_at = None
    alert.resolved_at = None
    for k, v in overrides.items():
        setattr(alert, k, v)
    return alert


@pytest.fixture
def as_trip_member():
    trip = make_mock_trip()
    app.dependency_overrides[require_trip_member] = lambda: trip
    app.dependency_overrides[get_db] = lambda: MagicMock()
    yield trip
    app.dependency_overrides.pop(require_trip_member, None)
    app.dependency_overrides.pop(get_db, None)


@pytest.fixture
def as_alert_member():
    alert = make_mock_alert()
    app.dependency_overrides[require_alert_member] = lambda: alert
    app.dependency_overrides[get_db] = lambda: MagicMock()
    yield alert
    app.dependency_overrides.pop(require_alert_member, None)
    app.dependency_overrides.pop(get_db, None)


@pytest.fixture
def no_group_membership():
    """Neither require_trip_member nor require_alert_member finds a
    membership row — simulates a user outside the alert's/trip's group."""
    mock_db = MagicMock()
    mock_db.scalars.return_value.first.return_value = None
    mock_db.get.return_value = None
    app.dependency_overrides[get_db] = lambda: mock_db
    yield
    app.dependency_overrides.pop(get_db, None)


# ---- GET /trips/{id}/alerts -------------------------------------------


def test_unauthenticated_cannot_list_trip_alerts():
    assert client.get(URL_LIST).status_code == 401


def test_non_member_cannot_list_trip_alerts(no_group_membership):
    token = make_token(sub=DEFAULT_TEST_USER_ID)
    response = client.get(URL_LIST, headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 404


@patch("app.api.alerts.alerts_service.list_alerts")
def test_member_can_list_trip_alerts(mock_list, as_trip_member):
    mock_list.return_value = [make_mock_alert()]
    token = make_token(sub=DEFAULT_TEST_USER_ID)

    response = client.get(URL_LIST, headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 200
    assert len(response.json()) == 1
    assert response.json()[0]["alert_type"] == "FALLING_BEHIND"


@patch("app.api.alerts.alerts_service.list_alerts")
def test_alert_filters_are_passed_through(mock_list, as_trip_member):
    mock_list.return_value = []
    token = make_token(sub=DEFAULT_TEST_USER_ID)

    response = client.get(
        f"{URL_LIST}?status=ACKNOWLEDGED&severity=WARNING&alert_type=SPEED_ANOMALY&limit=25",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    kwargs = mock_list.call_args.kwargs
    assert kwargs["status"] == AlertStatus.ACKNOWLEDGED
    assert kwargs["severity"] == AlertSeverity.WARNING
    assert kwargs["alert_type"] == AlertType.SPEED_ANOMALY
    assert kwargs["limit"] == 25


# ---- GET /trips/{id}/alerts/active --------------------------------------


@patch("app.api.alerts.alerts_service.list_active_alerts")
def test_active_alerts_endpoint_works(mock_list, as_trip_member):
    mock_list.return_value = [make_mock_alert(status=AlertStatus.ACKNOWLEDGED)]
    token = make_token(sub=DEFAULT_TEST_USER_ID)

    response = client.get(URL_ACTIVE, headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 200
    assert response.json()[0]["status"] == "ACKNOWLEDGED"


def test_non_member_cannot_access_active_alerts(no_group_membership):
    token = make_token(sub=DEFAULT_TEST_USER_ID)
    response = client.get(URL_ACTIVE, headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 404


# ---- GET /alerts/{id} -----------------------------------------------------


def test_unauthenticated_cannot_read_single_alert():
    assert client.get(URL_ONE).status_code == 401


def test_user_cannot_read_another_groups_alert(no_group_membership):
    """Security item 1: user cannot read another group's alert."""
    token = make_token(sub=DEFAULT_TEST_USER_ID)
    response = client.get(URL_ONE, headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 404


def test_member_can_read_alert(as_alert_member):
    token = make_token(sub=DEFAULT_TEST_USER_ID)
    response = client.get(URL_ONE, headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200
    assert response.json()["id"] == str(ALERT_ID)


# ---- POST /alerts/{id}/acknowledge -----------------------------------


def test_unauthenticated_cannot_acknowledge_alert():
    response = client.post(f"{URL_ONE}/acknowledge")
    assert response.status_code == 401


def test_user_cannot_acknowledge_another_groups_alert(no_group_membership):
    """Security item 2: user cannot acknowledge another group's alert."""
    token = make_token(sub=DEFAULT_TEST_USER_ID)
    response = client.post(f"{URL_ONE}/acknowledge", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 404


@patch("app.api.alerts._publish_alert_updated")
@patch("app.api.alerts.alerts_service.acknowledge_alert")
def test_member_can_acknowledge_alert(mock_ack, mock_publish, as_alert_member):
    mock_ack.return_value = make_mock_alert(status=AlertStatus.ACKNOWLEDGED)
    mock_publish.return_value = None
    token = make_token(sub=DEFAULT_TEST_USER_ID)

    response = client.post(f"{URL_ONE}/acknowledge", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 200
    assert response.json()["status"] == "ACKNOWLEDGED"
    mock_publish.assert_called_once()


# ---- POST /alerts/{id}/resolve -----------------------------------------


def test_unauthenticated_cannot_resolve_alert():
    response = client.post(f"{URL_ONE}/resolve")
    assert response.status_code == 401


def test_user_cannot_resolve_another_groups_alert(no_group_membership):
    """Security item 3: user cannot resolve another group's alert."""
    token = make_token(sub=DEFAULT_TEST_USER_ID)
    response = client.post(f"{URL_ONE}/resolve", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 404


@patch("app.api.alerts._publish_alert_updated")
@patch("app.api.alerts.alerts_service.resolve_alert")
def test_member_can_resolve_alert(mock_resolve, mock_publish, as_alert_member):
    mock_resolve.return_value = make_mock_alert(status=AlertStatus.RESOLVED)
    mock_publish.return_value = None
    token = make_token(sub=DEFAULT_TEST_USER_ID)

    response = client.post(f"{URL_ONE}/resolve", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 200
    assert response.json()["status"] == "RESOLVED"
    mock_publish.assert_called_once()


@patch("app.api.alerts.alerts_service.acknowledge_alert")
def test_acknowledging_already_acknowledged_alert_returns_409(mock_ack, as_alert_member):
    from app.core.errors import AppHTTPException

    mock_ack.side_effect = AppHTTPException(status_code=409, code="INVALID_ALERT_STATE", detail="already acknowledged")
    token = make_token(sub=DEFAULT_TEST_USER_ID)

    response = client.post(f"{URL_ONE}/acknowledge", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "INVALID_ALERT_STATE"


# ---- regression -------------------------------------------------------


def test_health_endpoint_still_works():
    response = client.get(f"{API}/health")
    assert response.status_code == 200
