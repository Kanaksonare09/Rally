"""
Endpoint-level tests for GPS ingestion: authentication, trip membership
authorization, and that service errors reach the client in the
standardized error shape. Ingestion/query *logic* is unit-tested against
location_service directly in test_location_service.py — these focus on
router wiring, following the same patched-service pattern as
test_trips_api.py (no live database in this environment).
"""

import uuid
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.core.config import settings
from app.core.database import get_db
from app.core.errors import AppHTTPException
from app.dependencies.trip import require_trip_member
from app.main import app
from app.models.enums import TripStatus
from tests.conftest import DEFAULT_TEST_USER_ID, make_token

client = TestClient(app)
API = settings.API_V1_STR
TRIP_ID = uuid.uuid4()
USER_ID = uuid.UUID(DEFAULT_TEST_USER_ID)
URL = f"{API}/trips/{TRIP_ID}/locations"


def make_mock_trip(status: TripStatus = TripStatus.ACTIVE) -> MagicMock:
    trip = MagicMock()
    trip.id = TRIP_ID
    trip.group_id = uuid.uuid4()
    trip.status = status
    return trip


def make_mock_location(**overrides) -> MagicMock:
    loc = MagicMock()
    loc.id = uuid.uuid4()
    loc.trip_id = TRIP_ID
    loc.user_id = USER_ID
    loc.latitude = 22.7196
    loc.longitude = 75.8577
    loc.accuracy = 8.5
    loc.speed = 12.4
    loc.heading = 180.0
    loc.recorded_at = datetime.now(timezone.utc)
    loc.created_at = datetime.now(timezone.utc)
    for key, value in overrides.items():
        setattr(loc, key, value)
    return loc


@pytest.fixture
def no_trip_membership():
    mock_db = MagicMock()
    mock_db.scalars.return_value.first.return_value = None
    app.dependency_overrides[get_db] = lambda: mock_db
    yield
    app.dependency_overrides.pop(get_db, None)


@pytest.fixture
def as_trip_member():
    def _apply(status: TripStatus = TripStatus.ACTIVE):
        trip = make_mock_trip(status)
        app.dependency_overrides[require_trip_member] = lambda: trip
        app.dependency_overrides[get_db] = lambda: MagicMock()
        return trip

    yield _apply
    app.dependency_overrides.pop(require_trip_member, None)
    app.dependency_overrides.pop(get_db, None)


VALID_BODY = {"latitude": 22.7196, "longitude": 75.8577, "accuracy": 8.5, "speed": 12.4, "heading": 180.0}


# ---- submit location: auth / membership -----------------------------------


def test_unauthenticated_user_cannot_submit_location():
    response = client.post(URL, json=VALID_BODY)
    assert response.status_code == 401


def test_non_member_cannot_submit_location(no_trip_membership):
    token = make_token(sub=DEFAULT_TEST_USER_ID)
    response = client.post(URL, headers={"Authorization": f"Bearer {token}"}, json=VALID_BODY)
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "TRIP_NOT_FOUND"


@patch("app.api.locations.location_service.record_location")
def test_active_member_can_submit_location(mock_record, as_trip_member):
    as_trip_member(TripStatus.ACTIVE)
    mock_record.return_value = make_mock_location()
    token = make_token(sub=DEFAULT_TEST_USER_ID)

    response = client.post(URL, headers={"Authorization": f"Bearer {token}"}, json=VALID_BODY)

    assert response.status_code == 201
    assert response.json()["latitude"] == 22.7196
    assert response.json()["longitude"] == 75.8577


@patch("app.api.locations.location_service.record_location")
def test_user_id_comes_from_authenticated_user_not_body(mock_record, as_trip_member):
    as_trip_member(TripStatus.ACTIVE)
    mock_record.return_value = make_mock_location()
    token = make_token(sub=DEFAULT_TEST_USER_ID)

    body = {**VALID_BODY, "user_id": str(uuid.uuid4())}  # not a real field, must be ignored
    client.post(URL, headers={"Authorization": f"Bearer {token}"}, json=body)

    called_user_id = mock_record.call_args.args[2]
    assert called_user_id == USER_ID


def test_location_create_schema_has_no_trusted_fields():
    from app.schemas.location import LocationCreate

    forbidden = {"id", "trip_id", "group_id", "user_id", "created_at"}
    assert forbidden.isdisjoint(LocationCreate.model_fields.keys())


# ---- submit location: trip state -------------------------------------------


@patch("app.api.locations.location_service.record_location")
def test_created_trip_rejects_location(mock_record, as_trip_member):
    as_trip_member(TripStatus.CREATED)
    mock_record.side_effect = AppHTTPException(
        status_code=409, code="INVALID_TRIP_STATE", detail="Location can only be submitted for an active trip."
    )
    token = make_token(sub=DEFAULT_TEST_USER_ID)

    response = client.post(URL, headers={"Authorization": f"Bearer {token}"}, json=VALID_BODY)

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "INVALID_TRIP_STATE"


@patch("app.api.locations.location_service.record_location")
def test_completed_trip_rejects_location(mock_record, as_trip_member):
    as_trip_member(TripStatus.COMPLETED)
    mock_record.side_effect = AppHTTPException(status_code=409, code="INVALID_TRIP_STATE", detail="rejected")
    token = make_token(sub=DEFAULT_TEST_USER_ID)

    response = client.post(URL, headers={"Authorization": f"Bearer {token}"}, json=VALID_BODY)
    assert response.status_code == 409


@patch("app.api.locations.location_service.record_location")
def test_cancelled_trip_rejects_location(mock_record, as_trip_member):
    as_trip_member(TripStatus.CANCELLED)
    mock_record.side_effect = AppHTTPException(status_code=409, code="INVALID_TRIP_STATE", detail="rejected")
    token = make_token(sub=DEFAULT_TEST_USER_ID)

    response = client.post(URL, headers={"Authorization": f"Bearer {token}"}, json=VALID_BODY)
    assert response.status_code == 409


# ---- submit location: validation -------------------------------------------


@pytest.mark.parametrize(
    "field,value",
    [
        ("latitude", 91),
        ("latitude", -91),
        ("longitude", 181),
        ("longitude", -181),
        ("accuracy", -1),
        ("speed", -1),
        ("heading", 360),
        ("heading", -1),
    ],
)
def test_invalid_field_values_return_422(as_trip_member, field, value):
    as_trip_member(TripStatus.ACTIVE)
    token = make_token(sub=DEFAULT_TEST_USER_ID)
    body = {**VALID_BODY, field: value}

    response = client.post(URL, headers={"Authorization": f"Bearer {token}"}, json=body)

    assert response.status_code == 422


# ---- get location history ---------------------------------------------------


@patch("app.api.locations.location_service.get_location_history")
def test_member_can_retrieve_location_history(mock_get, as_trip_member):
    as_trip_member(TripStatus.ACTIVE)
    mock_get.return_value = [make_mock_location()]
    token = make_token(sub=DEFAULT_TEST_USER_ID)

    response = client.get(URL, headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 200
    assert len(response.json()) == 1


def test_non_member_cannot_access_location_history(no_trip_membership):
    token = make_token(sub=DEFAULT_TEST_USER_ID)
    response = client.get(URL, headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 404


def test_unauthenticated_user_cannot_access_location_history():
    response = client.get(URL)
    assert response.status_code == 401


@patch("app.api.locations.location_service.get_location_history")
def test_history_supports_user_id_and_limit_query_params(mock_get, as_trip_member):
    as_trip_member(TripStatus.ACTIVE)
    mock_get.return_value = []
    token = make_token(sub=DEFAULT_TEST_USER_ID)
    target_user = uuid.uuid4()

    response = client.get(
        f"{URL}?user_id={target_user}&limit=50", headers={"Authorization": f"Bearer {token}"}
    )

    assert response.status_code == 200
    passed_query = mock_get.call_args.args[2]
    assert passed_query.user_id == target_user
    assert passed_query.limit == 50


def test_history_limit_over_maximum_is_rejected(as_trip_member):
    as_trip_member(TripStatus.ACTIVE)
    token = make_token(sub=DEFAULT_TEST_USER_ID)

    response = client.get(f"{URL}?limit=5001", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 422


def test_history_completed_trip_still_accessible(as_trip_member):
    """GET must work regardless of trip status — it also serves a
    finished trip's history for the trip-summary view."""
    as_trip_member(TripStatus.COMPLETED)
    with patch("app.api.locations.location_service.get_location_history", return_value=[]):
        token = make_token(sub=DEFAULT_TEST_USER_ID)
        response = client.get(URL, headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200


# ---- regression checks -------------------------------------------------


def test_health_endpoint_still_works():
    response = client.get(f"{API}/health")
    assert response.status_code == 200
