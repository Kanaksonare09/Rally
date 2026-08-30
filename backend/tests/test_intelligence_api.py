"""
Endpoint-level tests for the intelligence API: authorization (reusing
require_trip_member, same as trips/locations) and filter wiring. Service
calls are mocked — no live database/Redis required, same pattern as
test_trips_api.py / test_locations_api.py.
"""

import uuid
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.core.config import settings
from app.core.database import get_db
from app.dependencies.trip import require_trip_member
from app.main import app
from app.models.enums import IntelligenceEventType, IntelligenceSeverity
from tests.conftest import DEFAULT_TEST_USER_ID, make_token

client = TestClient(app)
API = settings.API_V1_STR
TRIP_ID = uuid.uuid4()
URL_STATE = f"{API}/trips/{TRIP_ID}/intelligence"
URL_EVENTS = f"{API}/trips/{TRIP_ID}/intelligence-events"


def make_mock_trip():
    trip = MagicMock()
    trip.id = TRIP_ID
    trip.group_id = uuid.uuid4()
    return trip


def make_mock_event(**overrides):
    event = MagicMock()
    event.id = uuid.uuid4()
    event.trip_id = TRIP_ID
    event.event_type = IntelligenceEventType.FALLING_BEHIND
    event.severity = IntelligenceSeverity.WARNING
    event.user_id = uuid.uuid4()
    event.related_user_id = None
    event.detected_at = datetime.now(timezone.utc)
    event.resolved_at = None
    event.event_metadata = {"distance_meters": 650, "threshold_meters": 500}
    for k, v in overrides.items():
        setattr(event, k, v)
    return event


@pytest.fixture
def as_trip_member():
    trip = make_mock_trip()
    app.dependency_overrides[require_trip_member] = lambda: trip
    app.dependency_overrides[get_db] = lambda: MagicMock()
    yield trip
    app.dependency_overrides.pop(require_trip_member, None)
    app.dependency_overrides.pop(get_db, None)


@pytest.fixture
def no_trip_membership():
    mock_db = MagicMock()
    mock_db.scalars.return_value.first.return_value = None
    app.dependency_overrides[get_db] = lambda: mock_db
    yield
    app.dependency_overrides.pop(get_db, None)


# ---- GET /trips/{id}/intelligence ------------------------------------


def test_unauthenticated_cannot_access_current_state():
    response = client.get(URL_STATE)
    assert response.status_code == 401


def test_non_member_cannot_access_current_state(no_trip_membership):
    token = make_token(sub=DEFAULT_TEST_USER_ID)
    response = client.get(URL_STATE, headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 404


@patch("app.api.intelligence.get_redis")
@patch("app.api.intelligence.events.list_active_events")
@patch("app.api.intelligence.engine.compute_current_state")
def test_member_can_access_current_state(mock_compute, mock_active, mock_redis, as_trip_member):
    from app.intelligence.engine import ComputedMember, ComputedState
    from app.intelligence.group_analysis import GroupAnalysisResult

    mock_compute.return_value = ComputedState(
        trip_id=TRIP_ID,
        group_id=as_trip_member.group_id,
        group_state="MOVING_TOGETHER",
        members=[
            ComputedMember(
                user_id="u1", name="Keshav", role="LEADER", movement_state="MOVING", presence="ONLINE",
                location_age_seconds=2.0, latitude=22.7, longitude=75.8, speed=5.0, accuracy=8.0,
                distance_from_group_center_meters=50.0, is_isolated=False, is_falling_behind=False,
            )
        ],
        group_analysis=GroupAnalysisResult(center=(22.7, 75.8), eligible_member_ids=["u1"], members={}, max_pairwise_distance_meters=0, is_cohesive=True, clusters=[["u1"]]),
    )
    mock_active.return_value = []
    token = make_token(sub=DEFAULT_TEST_USER_ID)

    response = client.get(URL_STATE, headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 200
    body = response.json()
    assert body["group_state"] == "MOVING_TOGETHER"
    assert body["members"][0]["name"] == "Keshav"
    assert body["active_events"] == []


@patch("app.api.intelligence.get_redis", side_effect=RuntimeError("no redis"))
def test_current_state_returns_503_when_redis_unavailable(mock_redis, as_trip_member):
    token = make_token(sub=DEFAULT_TEST_USER_ID)
    response = client.get(URL_STATE, headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "SERVICE_UNAVAILABLE"


# ---- GET /trips/{id}/intelligence-events ----------------------------


def test_unauthenticated_cannot_access_event_history():
    response = client.get(URL_EVENTS)
    assert response.status_code == 401


def test_non_member_cannot_access_event_history(no_trip_membership):
    token = make_token(sub=DEFAULT_TEST_USER_ID)
    response = client.get(URL_EVENTS, headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 404


@patch("app.api.intelligence.events.list_events")
def test_member_can_retrieve_event_history(mock_list, as_trip_member):
    mock_list.return_value = [make_mock_event()]
    token = make_token(sub=DEFAULT_TEST_USER_ID)

    response = client.get(URL_EVENTS, headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 200
    body = response.json()
    assert len(body) == 1
    assert body[0]["event_type"] == "FALLING_BEHIND"
    assert body[0]["metadata"] == {"distance_meters": 650, "threshold_meters": 500}


@patch("app.api.intelligence.events.list_events")
def test_event_history_filters_are_passed_through(mock_list, as_trip_member):
    mock_list.return_value = []
    token = make_token(sub=DEFAULT_TEST_USER_ID)
    target_user = uuid.uuid4()

    response = client.get(
        f"{URL_EVENTS}?event_type=SPEED_ANOMALY&severity=WARNING&user_id={target_user}&active_only=true&limit=10",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    call_kwargs = mock_list.call_args.kwargs
    assert call_kwargs["event_type"] == IntelligenceEventType.SPEED_ANOMALY
    assert call_kwargs["severity"] == IntelligenceSeverity.WARNING
    assert call_kwargs["user_id"] == target_user
    assert call_kwargs["active_only"] is True
    assert call_kwargs["limit"] == 10


def test_event_history_limit_over_maximum_is_rejected(as_trip_member):
    token = make_token(sub=DEFAULT_TEST_USER_ID)
    response = client.get(f"{URL_EVENTS}?limit=5000", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 422


def test_event_history_always_scoped_to_the_trip_in_the_url(as_trip_member):
    """Cross-trip access isn't possible through query params — list_events
    is always called with the trip_id from the URL, never a client value."""
    with patch("app.api.intelligence.events.list_events", return_value=[]) as mock_list:
        token = make_token(sub=DEFAULT_TEST_USER_ID)
        client.get(f"{URL_EVENTS}?event_type=FALLING_BEHIND", headers={"Authorization": f"Bearer {token}"})
        assert mock_list.call_args.args[1] == TRIP_ID


# ---- regression ----------------------------------------------------------


def test_health_endpoint_still_works():
    response = client.get(f"{API}/health")
    assert response.status_code == 200
