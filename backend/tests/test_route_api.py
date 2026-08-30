"""
Endpoint-level tests for app/api/route.py: authentication, leader-only
creation, and route/trip-state gating — following the same patched-
service-function pattern as test_trips_api.py/test_alerts_api.py (no live
database in this environment).
"""

import uuid
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from app.core.config import settings
from app.core.database import get_db
from app.dependencies.trip import require_trip_leader, require_trip_member
from app.main import app
from app.models.enums import MemberRole, RouteStatus, TripStatus
from tests.conftest import DEFAULT_TEST_USER_ID, make_token

client = TestClient(app)
API = settings.API_V1_STR
TRIP_ID = uuid.uuid4()
ROUTE_ID = uuid.uuid4()
USER_ID = uuid.UUID(DEFAULT_TEST_USER_ID)

VALID_BODY = {
    "name": "Manali trip",
    "origin_latitude": 12.90,
    "origin_longitude": 77.0,
    "destination_latitude": 12.91,
    "destination_longitude": 77.0,
    "coordinates": [[77.0, 12.90], [77.0, 12.905], [77.0, 12.91]],
    "estimated_duration_seconds": 600,
}


def make_mock_trip(**overrides) -> SimpleNamespace:
    trip = SimpleNamespace(id=TRIP_ID, group_id=uuid.uuid4(), status=TripStatus.CREATED)
    for k, v in overrides.items():
        setattr(trip, k, v)
    return trip


def make_mock_route(**overrides) -> SimpleNamespace:
    route = SimpleNamespace(
        id=ROUTE_ID, trip_id=TRIP_ID, name="Manali trip",
        origin_latitude=12.90, origin_longitude=77.0,
        destination_latitude=12.91, destination_longitude=77.0,
        coordinates=[[77.0, 12.90], [77.0, 12.91]],
        distance_meters=1112.0, estimated_duration_seconds=600,
        status=RouteStatus.PLANNED,
        created_at=datetime.now(timezone.utc), updated_at=datetime.now(timezone.utc),
    )
    for k, v in overrides.items():
        setattr(route, k, v)
    return route


@pytest.fixture
def as_trip_leader():
    trip = make_mock_trip()
    app.dependency_overrides[require_trip_leader] = lambda: trip
    app.dependency_overrides[get_db] = lambda: MagicMock()
    yield trip
    app.dependency_overrides.pop(require_trip_leader, None)
    app.dependency_overrides.pop(get_db, None)


@pytest.fixture
def as_trip_member():
    trip = make_mock_trip()
    app.dependency_overrides[require_trip_member] = lambda: trip
    app.dependency_overrides[get_db] = lambda: MagicMock()
    yield trip
    app.dependency_overrides.pop(require_trip_member, None)
    app.dependency_overrides.pop(get_db, None)


# ---- create route: auth ----------------------------------------------------


def test_unauthenticated_user_cannot_create_route():
    response = client.post(f"{API}/trips/{TRIP_ID}/route", json=VALID_BODY)
    assert response.status_code == 401


def test_plain_member_cannot_create_route():
    """require_trip_leader is unit-tested directly here (pure dependency
    logic), same pattern as test_trips_api.py's require_trip_creator_or_leader
    checks — no HTTP round trip needed for this part."""
    trip = SimpleNamespace()
    member = SimpleNamespace(user_id=USER_ID, role=MemberRole.MEMBER)
    with pytest.raises(HTTPException) as exc_info:
        require_trip_leader((trip, member))
    assert exc_info.value.status_code == 403


def test_leader_passes_require_trip_leader():
    trip = SimpleNamespace(marker="trip")
    member = SimpleNamespace(user_id=USER_ID, role=MemberRole.LEADER)
    assert require_trip_leader((trip, member)) is trip


@patch("app.api.route.route_service.create_or_replace_route")
def test_leader_can_create_route(mock_create, as_trip_leader):
    mock_create.return_value = make_mock_route()
    token = make_token(sub=DEFAULT_TEST_USER_ID)

    response = client.post(
        f"{API}/trips/{TRIP_ID}/route", headers={"Authorization": f"Bearer {token}"}, json=VALID_BODY
    )

    assert response.status_code == 201
    body = response.json()
    assert body["status"] == "PLANNED"
    assert body["coordinates"] == [[77.0, 12.90], [77.0, 12.91]]


@patch("app.api.route.route_service.create_or_replace_route")
def test_create_route_rejects_invalid_state_from_service(mock_create, as_trip_leader):
    from app.core.errors import AppHTTPException

    mock_create.side_effect = AppHTTPException(status_code=409, code="INVALID_TRIP_STATE", detail="bad state")
    token = make_token(sub=DEFAULT_TEST_USER_ID)

    response = client.post(
        f"{API}/trips/{TRIP_ID}/route", headers={"Authorization": f"Bearer {token}"}, json=VALID_BODY
    )

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "INVALID_TRIP_STATE"


def test_create_route_rejects_malformed_coordinate_pair(as_trip_leader):
    token = make_token(sub=DEFAULT_TEST_USER_ID)
    bad_body = {**VALID_BODY, "coordinates": [[77.0, 12.90, 99.0], [77.0, 12.91]]}
    response = client.post(f"{API}/trips/{TRIP_ID}/route", headers={"Authorization": f"Bearer {token}"}, json=bad_body)
    assert response.status_code == 422


def test_create_route_rejects_fewer_than_two_coordinates(as_trip_leader):
    token = make_token(sub=DEFAULT_TEST_USER_ID)
    bad_body = {**VALID_BODY, "coordinates": [[77.0, 12.90]]}
    response = client.post(f"{API}/trips/{TRIP_ID}/route", headers={"Authorization": f"Bearer {token}"}, json=bad_body)
    assert response.status_code == 422


# ---- get route ---------------------------------------------------------


@patch("app.api.route.route_service.get_route_by_trip")
def test_get_route_returns_404_when_none_planned(mock_get, as_trip_member):
    mock_get.return_value = None
    token = make_token(sub=DEFAULT_TEST_USER_ID)
    response = client.get(f"{API}/trips/{TRIP_ID}/route", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "ROUTE_NOT_FOUND"


@patch("app.api.route.route_service.get_route_by_trip")
def test_get_route_returns_existing_route(mock_get, as_trip_member):
    mock_get.return_value = make_mock_route()
    token = make_token(sub=DEFAULT_TEST_USER_ID)
    response = client.get(f"{API}/trips/{TRIP_ID}/route", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200
    assert response.json()["id"] == str(ROUTE_ID)


def test_unauthenticated_user_cannot_read_route():
    response = client.get(f"{API}/trips/{TRIP_ID}/route")
    assert response.status_code == 401


# ---- get route progress -------------------------------------------------


@patch("app.api.route.route_service.get_route_by_trip")
def test_progress_rejected_when_route_not_active(mock_get, as_trip_member):
    mock_get.return_value = make_mock_route(status=RouteStatus.PLANNED)
    token = make_token(sub=DEFAULT_TEST_USER_ID)
    response = client.get(f"{API}/trips/{TRIP_ID}/route/progress", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "ROUTE_NOT_ACTIVE"


@patch("app.api.route.route_service.get_live_route_progress", new_callable=AsyncMock)
@patch("app.api.route.route_service.get_route_by_trip")
@patch("app.api.route.get_redis")
def test_progress_returns_group_and_member_data_when_active(mock_get_redis, mock_get_route, mock_progress, as_trip_member):
    as_trip_member.status = TripStatus.ACTIVE
    mock_get_route.return_value = make_mock_route(status=RouteStatus.ACTIVE)
    mock_get_redis.return_value = MagicMock()

    member_progress = SimpleNamespace(
        user_id=str(USER_ID), name="Alice", role="LEADER", presence="ONLINE", location_age_seconds=2.0,
        match=SimpleNamespace(route_fraction=0.4, distance_traveled_meters=400.0, distance_remaining_meters=600.0, distance_from_route_meters=5.0),
        route_state="ON_ROUTE",
        eta=SimpleNamespace(eta_seconds=60.0, source="route_baseline"),
    )
    mock_progress.return_value = ([member_progress], 0.4, False)

    token = make_token(sub=DEFAULT_TEST_USER_ID)
    response = client.get(f"{API}/trips/{TRIP_ID}/route/progress", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 200
    body = response.json()
    assert body["group_route_fraction"] == 0.4
    assert body["trip_arrived"] is False
    assert body["leader"]["user_id"] == str(USER_ID)
    assert body["members"][0]["route_state"] == "ON_ROUTE"


# ---- regression --------------------------------------------------------


def test_health_endpoint_still_works():
    response = client.get(f"{API}/health")
    assert response.status_code == 200
