"""
Part 2 — input validation hardening. Most of this is *regression*
coverage proving RALLY's existing Pydantic constraints already reject
what this phase's checklist calls out (NaN, Infinity, out-of-range
coordinates) — see app/schemas/location.py for what actually enforces
each one. Deliberately does NOT introduce a second GPS validation system
— every assertion here exercises the same LocationCreate schema every
other phase's tests already use.

Trip/DB dependencies are overridden the same way test_locations_api.py
does it, so these tests only exercise validation, never a live database.
"""

import json
import logging
import uuid
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.core.config import settings
from app.core.database import get_db
from app.dependencies.auth import get_current_user_id
from app.dependencies.trip import require_trip_member
from app.main import app
from app.models.enums import TripStatus
from tests.conftest import DEFAULT_TEST_USER_ID, make_token

client = TestClient(app)
API = settings.API_V1_STR
TRIP_ID = uuid.uuid4()


def _auth_headers() -> dict:
    token = make_token(sub=DEFAULT_TEST_USER_ID)
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def as_trip_member():
    """Same pattern as test_locations_api.py — a mocked ACTIVE trip and
    DB session, so validation errors are reached without a live database."""
    trip = SimpleNamespace(id=TRIP_ID, group_id=uuid.uuid4(), status=TripStatus.ACTIVE)
    app.dependency_overrides[require_trip_member] = lambda: trip
    app.dependency_overrides[get_db] = lambda: MagicMock()
    yield trip
    app.dependency_overrides.pop(require_trip_member, None)
    app.dependency_overrides.pop(get_db, None)


@pytest.fixture
def as_authenticated_user():
    app.dependency_overrides[get_current_user_id] = lambda: DEFAULT_TEST_USER_ID
    app.dependency_overrides[get_db] = lambda: MagicMock()
    yield
    app.dependency_overrides.pop(get_current_user_id, None)
    app.dependency_overrides.pop(get_db, None)


# ---- NaN / Infinity / out-of-range coordinates -----------------------------


def test_nan_latitude_is_rejected(as_trip_member):
    response = client.post(
        f"{API}/trips/{TRIP_ID}/locations",
        headers=_auth_headers(),
        content=json.dumps({"latitude": float("nan"), "longitude": 0}),
    )
    assert response.status_code == 422


def test_infinite_longitude_is_rejected(as_trip_member):
    response = client.post(
        f"{API}/trips/{TRIP_ID}/locations",
        headers=_auth_headers(),
        content=json.dumps({"latitude": 0, "longitude": float("inf")}),
    )
    assert response.status_code == 422


def test_negative_infinity_is_rejected(as_trip_member):
    response = client.post(
        f"{API}/trips/{TRIP_ID}/locations",
        headers=_auth_headers(),
        content=json.dumps({"latitude": float("-inf"), "longitude": 0}),
    )
    assert response.status_code == 422


def test_out_of_range_latitude_is_rejected(as_trip_member):
    response = client.post(f"{API}/trips/{TRIP_ID}/locations", headers=_auth_headers(), json={"latitude": 999, "longitude": 0})
    assert response.status_code == 422


def test_negative_accuracy_is_rejected(as_trip_member):
    response = client.post(
        f"{API}/trips/{TRIP_ID}/locations", headers=_auth_headers(), json={"latitude": 0, "longitude": 0, "accuracy": -5}
    )
    assert response.status_code == 422


def test_invalid_uuid_in_path_is_rejected():
    response = client.get(f"{API}/trips/not-a-uuid/analytics", headers=_auth_headers())
    assert response.status_code == 422


# ---- pagination limits --------------------------------------------------


def test_history_limit_above_maximum_is_rejected(as_authenticated_user):
    response = client.get(f"{API}/users/me/trips?limit=100000", headers=_auth_headers())
    assert response.status_code == 422


def test_history_negative_offset_is_rejected(as_authenticated_user):
    response = client.get(f"{API}/users/me/trips?offset=-1", headers=_auth_headers())
    assert response.status_code == 422


# ---- request body size ---------------------------------------------------


def test_oversized_request_body_is_rejected(as_trip_member, monkeypatch):
    monkeypatch.setattr(settings, "MAX_REQUEST_BODY_BYTES", 100)
    response = client.post(
        f"{API}/trips/{TRIP_ID}/locations",
        headers={**_auth_headers(), "Content-Length": "1000000"},
        content=b"x" * 1000,
    )
    assert response.status_code == 413
    assert response.json()["error"]["code"] == "PAYLOAD_TOO_LARGE"


@patch("app.api.locations.location_service.record_location")
def test_normal_sized_body_is_unaffected_by_the_limit(mock_record, as_trip_member):
    from datetime import datetime, timezone

    mock_record.return_value = SimpleNamespace(
        id=uuid.uuid4(), trip_id=TRIP_ID, user_id=uuid.UUID(DEFAULT_TEST_USER_ID),
        latitude=0.0, longitude=0.0, accuracy=None, speed=None, heading=None,
        recorded_at=datetime.now(timezone.utc), created_at=datetime.now(timezone.utc),
    )
    response = client.post(f"{API}/trips/{TRIP_ID}/locations", headers=_auth_headers(), json={"latitude": 0, "longitude": 0})
    assert response.status_code == 201


# ---- logs never contain secrets --------------------------------------------


def test_request_logs_never_contain_the_bearer_token(caplog):
    token = make_token(sub=DEFAULT_TEST_USER_ID)
    with caplog.at_level(logging.DEBUG):
        client.get(f"{API}/health", headers={"Authorization": f"Bearer {token}"})
    for record in caplog.records:
        assert token not in record.getMessage()
        assert "Bearer" not in record.getMessage()
