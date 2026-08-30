"""
Endpoint-level tests for the SOS API: authentication, trip/group
authorization, GPS validation, and the explicit security checks this
phase requires (no cross-trip/cross-group access, no impersonation).
Service calls mocked — no live database/Redis required.
"""

import uuid
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.core.config import settings
from app.core.database import get_db
from app.dependencies.sos import require_sos_member
from app.dependencies.trip import require_trip_member
from app.main import app
from app.models.enums import SOSStatus, TripStatus
from tests.conftest import DEFAULT_TEST_USER_ID, make_token

client = TestClient(app)
API = settings.API_V1_STR
TRIP_ID = uuid.uuid4()
SOS_ID = uuid.uuid4()
URL_TRIGGER = f"{API}/trips/{TRIP_ID}/sos"
URL_LIST = f"{API}/trips/{TRIP_ID}/sos"
URL_ACTIVE = f"{API}/trips/{TRIP_ID}/sos/active"
URL_ONE = f"{API}/sos/{SOS_ID}"

VALID_BODY = {"latitude": 22.7196, "longitude": 75.8577, "accuracy": 8.5, "message": "Need help"}


def make_mock_trip(status=TripStatus.ACTIVE):
    trip = MagicMock()
    trip.id = TRIP_ID
    trip.group_id = uuid.uuid4()
    trip.status = status
    return trip


def make_mock_sos(**overrides):
    sos = MagicMock()
    sos.id = SOS_ID
    sos.trip_id = TRIP_ID
    sos.user_id = uuid.uuid4()
    sos.latitude = 22.7196
    sos.longitude = 75.8577
    sos.accuracy = 8.5
    sos.message = "Need help"
    sos.status = SOSStatus.ACTIVE
    sos.sos_metadata = {}
    sos.triggered_at = datetime.now(timezone.utc)
    sos.acknowledged_at = None
    sos.resolved_at = None
    sos.created_at = datetime.now(timezone.utc)
    for k, v in overrides.items():
        setattr(sos, k, v)
    return sos


@pytest.fixture
def as_trip_member():
    trip = make_mock_trip()
    app.dependency_overrides[require_trip_member] = lambda: trip
    app.dependency_overrides[get_db] = lambda: MagicMock()
    yield trip
    app.dependency_overrides.pop(require_trip_member, None)
    app.dependency_overrides.pop(get_db, None)


@pytest.fixture
def as_sos_member():
    sos = make_mock_sos()
    app.dependency_overrides[require_sos_member] = lambda: sos
    app.dependency_overrides[get_db] = lambda: MagicMock()
    yield sos
    app.dependency_overrides.pop(require_sos_member, None)
    app.dependency_overrides.pop(get_db, None)


@pytest.fixture
def no_group_membership():
    mock_db = MagicMock()
    mock_db.scalars.return_value.first.return_value = None
    mock_db.get.return_value = None
    app.dependency_overrides[get_db] = lambda: mock_db
    yield
    app.dependency_overrides.pop(get_db, None)


# ---- POST /trips/{id}/sos --------------------------------------------


def test_unauthenticated_user_cannot_trigger_sos():
    response = client.post(URL_TRIGGER, json=VALID_BODY)
    assert response.status_code == 401


def test_non_member_cannot_trigger_sos(no_group_membership):
    token = make_token(sub=DEFAULT_TEST_USER_ID)
    response = client.post(URL_TRIGGER, headers={"Authorization": f"Bearer {token}"}, json=VALID_BODY)
    assert response.status_code == 404


@patch("app.api.sos.sos_service.trigger_sos")
def test_authenticated_member_can_trigger_sos(mock_trigger, as_trip_member):
    mock_trigger.return_value = make_mock_sos()
    token = make_token(sub=DEFAULT_TEST_USER_ID)

    response = client.post(URL_TRIGGER, headers={"Authorization": f"Bearer {token}"}, json=VALID_BODY)

    assert response.status_code == 201
    assert response.json()["status"] == "ACTIVE"


def test_sos_rejected_for_inactive_trip(as_trip_member):
    as_trip_member.status = TripStatus.CREATED
    token = make_token(sub=DEFAULT_TEST_USER_ID)

    response = client.post(URL_TRIGGER, headers={"Authorization": f"Bearer {token}"}, json=VALID_BODY)

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "TRIP_NOT_ACTIVE"


@patch("app.api.sos.sos_service.trigger_sos")
def test_client_cannot_spoof_user_id(mock_trigger, as_trip_member):
    """Security items 8/11: user cannot submit SOS for another user —
    there's no user_id field on SOSCreate to smuggle one in through, and
    the service is always called with the authenticated user's own id."""
    mock_trigger.return_value = make_mock_sos()
    token = make_token(sub=DEFAULT_TEST_USER_ID)

    body = {**VALID_BODY, "user_id": str(uuid.uuid4())}
    client.post(URL_TRIGGER, headers={"Authorization": f"Bearer {token}"}, json=body)

    called_user_id = mock_trigger.call_args.args[4]
    assert str(called_user_id) == DEFAULT_TEST_USER_ID


@patch("app.api.sos.sos_service.trigger_sos")
def test_client_cannot_spoof_group_id_or_trip_id(mock_trigger, as_trip_member):
    """Security items 9/10: trip_id/group_id always come from the
    authorized trip context, never the request body."""
    mock_trigger.return_value = make_mock_sos()
    token = make_token(sub=DEFAULT_TEST_USER_ID)

    body = {**VALID_BODY, "trip_id": str(uuid.uuid4()), "group_id": str(uuid.uuid4())}
    client.post(URL_TRIGGER, headers={"Authorization": f"Bearer {token}"}, json=body)

    called_trip_id, called_group_id = mock_trigger.call_args.args[2], mock_trigger.call_args.args[3]
    assert called_trip_id == TRIP_ID
    assert called_group_id == as_trip_member.group_id


@pytest.mark.parametrize(
    "field,value",
    [("latitude", 91), ("latitude", -91), ("longitude", 181), ("longitude", -181), ("accuracy", -1)],
)
def test_invalid_gps_fields_rejected(as_trip_member, field, value):
    token = make_token(sub=DEFAULT_TEST_USER_ID)
    body = {**VALID_BODY, field: value}

    response = client.post(URL_TRIGGER, headers={"Authorization": f"Bearer {token}"}, json=body)

    assert response.status_code == 422


# ---- GET /trips/{id}/sos, /sos/active ----------------------------------


@patch("app.api.sos.sos_service.list_sos")
def test_sos_history_endpoint_works(mock_list, as_trip_member):
    mock_list.return_value = [make_mock_sos()]
    token = make_token(sub=DEFAULT_TEST_USER_ID)

    response = client.get(URL_LIST, headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 200
    assert len(response.json()) == 1


@patch("app.api.sos.sos_service.list_active_sos")
def test_active_sos_endpoint_works(mock_list, as_trip_member):
    mock_list.return_value = [make_mock_sos()]
    token = make_token(sub=DEFAULT_TEST_USER_ID)

    response = client.get(URL_ACTIVE, headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 200
    assert response.json()[0]["status"] == "ACTIVE"


def test_non_member_cannot_access_sos_history(no_group_membership):
    token = make_token(sub=DEFAULT_TEST_USER_ID)
    response = client.get(URL_LIST, headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 404


# ---- POST /sos/{id}/acknowledge, /resolve, /cancel -----------------------


def test_user_cannot_access_another_groups_sos(no_group_membership):
    """Security item 4: user cannot access another group's SOS."""
    token = make_token(sub=DEFAULT_TEST_USER_ID)
    response = client.post(f"{URL_ONE}/acknowledge", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 404


@patch("app.api.sos.sos_service.acknowledge_sos")
def test_member_can_acknowledge_sos(mock_ack, as_sos_member):
    mock_ack.return_value = make_mock_sos(status=SOSStatus.ACKNOWLEDGED)
    token = make_token(sub=DEFAULT_TEST_USER_ID)

    response = client.post(f"{URL_ONE}/acknowledge", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 200
    assert response.json()["status"] == "ACKNOWLEDGED"


def test_user_cannot_resolve_another_groups_sos(no_group_membership):
    """Security item 6: user cannot resolve another group's SOS."""
    token = make_token(sub=DEFAULT_TEST_USER_ID)
    response = client.post(f"{URL_ONE}/resolve", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 404


@patch("app.api.sos.sos_service.resolve_sos")
def test_member_can_resolve_sos(mock_resolve, as_sos_member):
    mock_resolve.return_value = make_mock_sos(status=SOSStatus.RESOLVED)
    token = make_token(sub=DEFAULT_TEST_USER_ID)

    response = client.post(f"{URL_ONE}/resolve", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 200
    assert response.json()["status"] == "RESOLVED"


@patch("app.api.sos.sos_service.cancel_sos")
def test_creator_can_cancel_own_sos(mock_cancel, as_sos_member):
    mock_cancel.return_value = make_mock_sos(status=SOSStatus.CANCELLED)
    token = make_token(sub=DEFAULT_TEST_USER_ID)

    response = client.post(f"{URL_ONE}/cancel", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 200
    # The endpoint always passes the *authenticated* user id, never a
    # client-supplied one — service.cancel_sos enforces creator-only.
    called_user_id = mock_cancel.call_args.args[3]
    assert str(called_user_id) == DEFAULT_TEST_USER_ID


@patch("app.api.sos.sos_service.cancel_sos")
def test_non_creator_cannot_cancel_sos(mock_cancel, as_sos_member):
    """Security item 7: user cannot cancel another user's SOS — enforced
    in the service layer (test_sos_service.py), surfaced here as a 403."""
    from app.core.errors import AppHTTPException

    mock_cancel.side_effect = AppHTTPException(
        status_code=403, code="FORBIDDEN", detail="Only the person who triggered this SOS can cancel it."
    )
    token = make_token(sub=DEFAULT_TEST_USER_ID)

    response = client.post(f"{URL_ONE}/cancel", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 403


def test_unauthenticated_cannot_cancel_sos():
    response = client.post(f"{URL_ONE}/cancel")
    assert response.status_code == 401


# ---- regression -------------------------------------------------------


def test_health_endpoint_still_works():
    response = client.get(f"{API}/health")
    assert response.status_code == 200
