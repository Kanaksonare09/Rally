"""
Endpoint-level tests for trip management: authentication, group/trip
membership authorization, and that service errors reach the client in the
standardized error shape. Trip lifecycle *logic* (state transitions, the
active-trip-per-group rule, the DB-race fallback) is unit-tested against
trip_service directly in test_trip_service.py — these tests focus on
router wiring instead, following the same patched-service-function pattern
as test_groups_api.py (there's no live database in this environment).
"""

import uuid
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from app.core.config import settings
from app.core.database import get_db
from app.core.errors import AppHTTPException
from app.dependencies.auth import get_current_profile
from app.dependencies.group import require_group_member
from app.dependencies.trip import require_trip_creator_or_leader, require_trip_member
from app.main import app
from app.models.enums import MemberRole, MemberStatus, TripStatus
from tests.conftest import DEFAULT_TEST_USER_ID, make_token

client = TestClient(app)
API = settings.API_V1_STR
GROUP_ID = uuid.uuid4()
TRIP_ID = uuid.uuid4()
USER_ID = uuid.UUID(DEFAULT_TEST_USER_ID)


def make_mock_trip(**overrides) -> MagicMock:
    trip = MagicMock()
    trip.id = TRIP_ID
    trip.group_id = GROUP_ID
    trip.status = TripStatus.CREATED
    trip.started_by = USER_ID
    trip.started_at = None
    trip.ended_at = None
    trip.destination_name = "Solang Valley"
    trip.distance = None
    trip.duration = None
    trip.safety_score = None
    trip.created_at = datetime.now(timezone.utc)
    for key, value in overrides.items():
        setattr(trip, key, value)
    return trip


@pytest.fixture
def fake_profile_override():
    fake_profile = SimpleNamespace(id=USER_ID, full_name="Test User", avatar_url=None)
    app.dependency_overrides[get_current_profile] = lambda: fake_profile
    yield fake_profile
    app.dependency_overrides.pop(get_current_profile, None)


@pytest.fixture
def no_group_membership():
    """Real require_group_member dependency runs, but its DB lookup finds
    no membership row — the not-a-member / group-doesn't-exist path."""
    mock_db = MagicMock()
    mock_db.scalars.return_value.first.return_value = None
    app.dependency_overrides[get_db] = lambda: mock_db
    yield
    app.dependency_overrides.pop(get_db, None)


@pytest.fixture
def as_group_member():
    mock_member = MagicMock(user_id=USER_ID, role=MemberRole.MEMBER, status=MemberStatus.ACTIVE)
    app.dependency_overrides[require_group_member] = lambda: mock_member
    app.dependency_overrides[get_db] = lambda: MagicMock()
    yield mock_member
    app.dependency_overrides.pop(require_group_member, None)
    app.dependency_overrides.pop(get_db, None)


@pytest.fixture
def as_trip_member():
    trip = make_mock_trip()
    app.dependency_overrides[require_trip_member] = lambda: trip
    app.dependency_overrides[get_db] = lambda: MagicMock()
    yield trip
    app.dependency_overrides.pop(require_trip_member, None)
    app.dependency_overrides.pop(get_db, None)


@pytest.fixture
def as_trip_creator_or_leader():
    trip = make_mock_trip()
    app.dependency_overrides[require_trip_creator_or_leader] = lambda: trip
    app.dependency_overrides[get_db] = lambda: MagicMock()
    yield trip
    app.dependency_overrides.pop(require_trip_creator_or_leader, None)
    app.dependency_overrides.pop(get_db, None)


# ---- create trip -----------------------------------------------------


def test_unauthenticated_user_cannot_create_trip():
    response = client.post(f"{API}/groups/{GROUP_ID}/trips", json={})
    assert response.status_code == 401


def test_non_member_cannot_create_trip(no_group_membership):
    token = make_token(sub=DEFAULT_TEST_USER_ID)
    response = client.post(
        f"{API}/groups/{GROUP_ID}/trips",
        headers={"Authorization": f"Bearer {token}"},
        json={},
    )
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "GROUP_NOT_FOUND"


@patch("app.api.trips.trip_service.create_trip")
def test_active_member_can_create_trip(mock_create, as_group_member, fake_profile_override):
    mock_create.return_value = make_mock_trip(status=TripStatus.CREATED)
    token = make_token(sub=DEFAULT_TEST_USER_ID)

    response = client.post(
        f"{API}/groups/{GROUP_ID}/trips",
        headers={"Authorization": f"Bearer {token}"},
        json={"destination_name": "Solang Valley"},
    )

    assert response.status_code == 201
    assert response.json()["status"] == "CREATED"


@patch("app.api.trips.trip_service.create_trip")
def test_creator_is_stored_as_authenticated_user_not_request_body(mock_create, as_group_member):
    mock_create.return_value = make_mock_trip()
    token = make_token(sub=DEFAULT_TEST_USER_ID)

    client.post(
        f"{API}/groups/{GROUP_ID}/trips",
        headers={"Authorization": f"Bearer {token}"},
        # started_by / status / id are not fields on TripCreate at all, so
        # even trying to smuggle them in has no effect — extra keys are
        # silently ignored by the schema, never reach the service call.
        json={"destination_name": "Solang Valley", "started_by": str(uuid.uuid4()), "status": "ACTIVE"},
    )

    called_group_id, called_user_id = mock_create.call_args.args[1], mock_create.call_args.args[2]
    assert called_group_id == GROUP_ID
    assert called_user_id == USER_ID


# ---- list group trips ----------------------------------------------------


@patch("app.api.trips.trip_service.list_group_trips")
def test_group_member_can_list_group_trips(mock_list, as_group_member):
    mock_list.return_value = [make_mock_trip(status=TripStatus.COMPLETED)]
    token = make_token(sub=DEFAULT_TEST_USER_ID)

    response = client.get(f"{API}/groups/{GROUP_ID}/trips", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 200
    assert len(response.json()) == 1


def test_non_member_cannot_list_group_trips(no_group_membership):
    token = make_token(sub=DEFAULT_TEST_USER_ID)
    response = client.get(f"{API}/groups/{GROUP_ID}/trips", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 404


# ---- get single trip -------------------------------------------------


def test_member_can_retrieve_trip(as_trip_member):
    token = make_token(sub=DEFAULT_TEST_USER_ID)
    response = client.get(f"{API}/trips/{TRIP_ID}", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200
    assert response.json()["id"] == str(TRIP_ID)


@patch("app.dependencies.trip.trip_service.get_trip_by_id")
def test_non_member_cannot_retrieve_trip(mock_get_trip):
    mock_get_trip.return_value = make_mock_trip()
    mock_db = MagicMock()
    mock_db.scalars.return_value.first.return_value = None  # no membership row
    app.dependency_overrides[get_db] = lambda: mock_db
    token = make_token(sub=DEFAULT_TEST_USER_ID)

    response = client.get(f"{API}/trips/{TRIP_ID}", headers={"Authorization": f"Bearer {token}"})

    app.dependency_overrides.pop(get_db, None)
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "TRIP_NOT_FOUND"


# ---- start trip ------------------------------------------------------


@patch("app.api.trips.trip_service.start_trip")
def test_created_trip_can_be_started_and_becomes_active(mock_start, as_trip_member):
    mock_start.return_value = make_mock_trip(status=TripStatus.ACTIVE, started_at=datetime.now(timezone.utc))
    token = make_token(sub=DEFAULT_TEST_USER_ID)

    response = client.post(f"{API}/trips/{TRIP_ID}/start", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ACTIVE"
    assert body["started_at"] is not None


@patch("app.api.trips.trip_service.start_trip")
def test_starting_an_already_active_trip_returns_invalid_state(mock_start, as_trip_member):
    mock_start.side_effect = AppHTTPException(status_code=409, code="INVALID_TRIP_STATE", detail="bad transition")
    token = make_token(sub=DEFAULT_TEST_USER_ID)

    response = client.post(f"{API}/trips/{TRIP_ID}/start", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "INVALID_TRIP_STATE"


@patch("app.api.trips.trip_service.start_trip")
def test_starting_trip_when_group_already_has_active_trip_returns_active_trip_exists(mock_start, as_trip_member):
    mock_start.side_effect = AppHTTPException(
        status_code=409, code="ACTIVE_TRIP_EXISTS", detail="This group already has an active trip."
    )
    token = make_token(sub=DEFAULT_TEST_USER_ID)

    response = client.post(f"{API}/trips/{TRIP_ID}/start", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 409
    assert response.json() == {
        "success": False,
        "error": {"code": "ACTIVE_TRIP_EXISTS", "message": "This group already has an active trip."},
    }


# ---- end trip --------------------------------------------------------


@patch("app.api.trips.trip_service.end_trip")
def test_active_trip_can_be_completed(mock_end, as_trip_member):
    mock_end.return_value = make_mock_trip(status=TripStatus.COMPLETED, ended_at=datetime.now(timezone.utc))
    token = make_token(sub=DEFAULT_TEST_USER_ID)

    response = client.post(f"{API}/trips/{TRIP_ID}/end", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 200
    assert response.json()["status"] == "COMPLETED"


# ---- cancel trip -------------------------------------------------------


@patch("app.api.trips.trip_service.cancel_trip")
def test_created_trip_can_be_cancelled(mock_cancel, as_trip_creator_or_leader):
    mock_cancel.return_value = make_mock_trip(status=TripStatus.CANCELLED)
    token = make_token(sub=DEFAULT_TEST_USER_ID)

    response = client.post(f"{API}/trips/{TRIP_ID}/cancel", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 200
    assert response.json()["status"] == "CANCELLED"


@patch("app.api.trips.trip_service.cancel_trip")
def test_active_trip_cannot_be_cancelled(mock_cancel, as_trip_creator_or_leader):
    mock_cancel.side_effect = AppHTTPException(status_code=409, code="INVALID_TRIP_STATE", detail="bad transition")
    token = make_token(sub=DEFAULT_TEST_USER_ID)

    response = client.post(f"{API}/trips/{TRIP_ID}/cancel", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "INVALID_TRIP_STATE"


# ---- creator-or-leader authorization (pure dependency logic) ------------


def test_trip_creator_can_cancel_even_if_not_leader():
    trip = SimpleNamespace(started_by=USER_ID)
    member = SimpleNamespace(user_id=USER_ID, role=MemberRole.MEMBER)
    assert require_trip_creator_or_leader((trip, member)) is trip


def test_group_leader_can_cancel_even_if_not_creator():
    trip = SimpleNamespace(started_by=uuid.uuid4())
    member = SimpleNamespace(user_id=USER_ID, role=MemberRole.LEADER)
    assert require_trip_creator_or_leader((trip, member)) is trip


def test_plain_member_cannot_cancel_someone_elses_trip():
    trip = SimpleNamespace(started_by=uuid.uuid4())
    member = SimpleNamespace(user_id=USER_ID, role=MemberRole.MEMBER)
    with pytest.raises(HTTPException) as exc_info:
        require_trip_creator_or_leader((trip, member))
    assert exc_info.value.status_code == 403


# ---- regression checks -------------------------------------------------


def test_health_endpoint_still_works():
    response = client.get(f"{API}/health")
    assert response.status_code == 200
