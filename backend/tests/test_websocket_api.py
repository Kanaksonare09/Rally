"""
Endpoint-level WebSocket tests via TestClient.websocket_connect() — real
JWT verification, fakeredis standing in for Redis, and a fake DB session
standing in for Postgres (no live database — see backend README, same
approach as the REST endpoint test suites).
"""

import uuid
from types import SimpleNamespace
from unittest.mock import patch

import fakeredis
import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from app.core.config import settings
from app.main import app
from app.models.enums import MemberRole, MemberStatus, TripStatus
from tests.conftest import DEFAULT_TEST_USER_ID, make_token

client = TestClient(app)

TRIP_ID = uuid.uuid4()
GROUP_ID = uuid.uuid4()
USER_ID = uuid.UUID(DEFAULT_TEST_USER_ID)
WS_URL = f"{settings.API_V1_STR}/ws/trips/{TRIP_ID}"


class _ScalarResult:
    def __init__(self, value):
        self._value = value

    def first(self):
        return self._value


class _ExecuteResult:
    def __init__(self, rows):
        self._rows = rows

    def all(self):
        return self._rows


class FakeSession:
    """Backs both authorize_connection() (get/scalars) and
    build_trip_state_snapshot() (execute...all) with canned data."""

    def __init__(self, trip=None, member=None, member_rows=None):
        self._trip = trip
        self._member = member
        self._member_rows = member_rows or []
        self.closed = False

    def get(self, model, pk):
        return self._trip

    def scalars(self, stmt):
        return _ScalarResult(self._member)

    def execute(self, stmt):
        return _ExecuteResult(self._member_rows)

    def close(self):
        self.closed = True


def make_trip(status=TripStatus.ACTIVE):
    return SimpleNamespace(id=TRIP_ID, group_id=GROUP_ID, status=status)


def make_member(status=MemberStatus.ACTIVE, role=MemberRole.MEMBER):
    return SimpleNamespace(user_id=USER_ID, role=role, status=status)


def _receive_until(ws, message_type: str, max_frames: int = 5) -> dict:
    """Reads frames until one of `message_type` arrives. Connections carry
    interleaved presence/broadcast traffic, so tests that care about one
    specific frame shouldn't assert on exact arrival order."""
    for _ in range(max_frames):
        message = ws.receive_json()
        if message["type"] == message_type:
            return message
    raise AssertionError(f"Never received a {message_type!r} frame within {max_frames} frames")


@pytest.fixture
def fake_redis_client():
    return fakeredis.FakeAsyncRedis(decode_responses=True)


def _patched(redis, session):
    """Patches exactly the two external dependencies the WS route can't
    function without in this environment: the shared Redis client and the
    DB session factory."""
    return patch("app.api.websocket.get_redis", return_value=redis), patch(
        "app.api.websocket.SessionLocal", return_value=session
    )


# ---- connect-time auth / authorization -------------------------------------


def test_unauthenticated_connection_is_rejected(fake_redis_client):
    with patch("app.api.websocket.get_redis", return_value=fake_redis_client):
        with client.websocket_connect(WS_URL) as ws:
            message = ws.receive_json()
            assert message["type"] == "error"
            assert message["data"]["code"] == "UNAUTHORIZED"
            with pytest.raises(WebSocketDisconnect):
                ws.receive_json()


def test_invalid_jwt_is_rejected(fake_redis_client):
    with patch("app.api.websocket.get_redis", return_value=fake_redis_client):
        with client.websocket_connect(f"{WS_URL}?token=not-a-real-jwt") as ws:
            message = ws.receive_json()
            assert message["data"]["code"] == "UNAUTHORIZED"


def test_expired_jwt_is_rejected(fake_redis_client):
    token = make_token(expires_in_seconds=-60)
    with patch("app.api.websocket.get_redis", return_value=fake_redis_client):
        with client.websocket_connect(f"{WS_URL}?token={token}") as ws:
            assert ws.receive_json()["data"]["code"] == "UNAUTHORIZED"


def test_nonexistent_trip_is_rejected(fake_redis_client):
    token = make_token(sub=DEFAULT_TEST_USER_ID)
    session = FakeSession(trip=None, member=None)
    p1, p2 = _patched(fake_redis_client, session)
    with p1, p2:
        with client.websocket_connect(f"{WS_URL}?token={token}") as ws:
            assert ws.receive_json()["data"]["code"] == "TRIP_NOT_FOUND"


def test_non_member_is_rejected(fake_redis_client):
    """User cannot connect to another group's trip."""
    token = make_token(sub=DEFAULT_TEST_USER_ID)
    session = FakeSession(trip=make_trip(), member=None)
    p1, p2 = _patched(fake_redis_client, session)
    with p1, p2:
        with client.websocket_connect(f"{WS_URL}?token={token}") as ws:
            assert ws.receive_json()["data"]["code"] == "NOT_A_MEMBER"


def test_inactive_trip_is_rejected_for_a_real_member(fake_redis_client):
    token = make_token(sub=DEFAULT_TEST_USER_ID)
    session = FakeSession(trip=make_trip(status=TripStatus.CREATED), member=make_member())
    p1, p2 = _patched(fake_redis_client, session)
    with p1, p2:
        with client.websocket_connect(f"{WS_URL}?token={token}") as ws:
            assert ws.receive_json()["data"]["code"] == "TRIP_NOT_ACTIVE"


def test_active_member_can_connect_to_active_trip(fake_redis_client):
    token = make_token(sub=DEFAULT_TEST_USER_ID)
    session = FakeSession(
        trip=make_trip(status=TripStatus.ACTIVE),
        member=make_member(),
        member_rows=[(make_member(role=MemberRole.LEADER), SimpleNamespace(full_name="Keshav"))],
    )
    p1, p2 = _patched(fake_redis_client, session)
    with p1, p2:
        with client.websocket_connect(f"{WS_URL}?token={token}") as ws:
            snapshot = ws.receive_json()
            assert snapshot["type"] == "trip_state"
            assert snapshot["data"]["trip_id"] == str(TRIP_ID)
            assert snapshot["data"]["members"][0]["name"] == "Keshav"
            assert snapshot["data"]["members"][0]["role"] == "LEADER"


# ---- messages after connecting ---------------------------------------------


def _connected_session():
    return FakeSession(
        trip=make_trip(status=TripStatus.ACTIVE),
        member=make_member(),
        member_rows=[],
    )


def test_heartbeat_returns_heartbeat_ack(fake_redis_client):
    token = make_token(sub=DEFAULT_TEST_USER_ID)
    p1, p2 = _patched(fake_redis_client, _connected_session())
    with p1, p2:
        with client.websocket_connect(f"{WS_URL}?token={token}") as ws:
            ws.receive_json()  # trip_state snapshot
            ws.send_json({"type": "heartbeat"})
            assert ws.receive_json()["type"] == "heartbeat_ack"


@patch("app.websocket.handlers.trip_service.get_trip_by_id")
@patch("app.websocket.handlers.location_service.record_location")
def test_valid_location_update_returns_location_ack(mock_record, mock_get_trip, fake_redis_client):
    from datetime import datetime, timezone

    mock_get_trip.return_value = make_trip(status=TripStatus.ACTIVE)
    mock_record.return_value = SimpleNamespace(
        latitude=22.7196, longitude=75.8577, accuracy=8.5, speed=12.4, heading=180.0,
        recorded_at=datetime.now(timezone.utc),
    )

    token = make_token(sub=DEFAULT_TEST_USER_ID)
    p1, p2 = _patched(fake_redis_client, _connected_session())
    with p1, p2:
        with client.websocket_connect(f"{WS_URL}?token={token}") as ws:
            ws.receive_json()  # trip_state snapshot
            ws.send_json({"type": "location_update", "data": {"latitude": 22.7196, "longitude": 75.8577}})
            response = ws.receive_json()
            assert response["type"] == "location_ack"
            assert response["data"]["accepted"] is True


def test_invalid_location_returns_error_not_disconnect(fake_redis_client):
    """A single malformed message shouldn't kill the connection — the
    client should be able to keep talking after an error frame."""
    token = make_token(sub=DEFAULT_TEST_USER_ID)
    p1, p2 = _patched(fake_redis_client, _connected_session())
    with p1, p2:
        with client.websocket_connect(f"{WS_URL}?token={token}") as ws:
            ws.receive_json()  # trip_state snapshot
            ws.send_json({"type": "location_update", "data": {"latitude": 999, "longitude": 0}})
            error = ws.receive_json()
            assert error["data"]["code"] == "INVALID_LOCATION"

            ws.send_json({"type": "heartbeat"})
            assert ws.receive_json()["type"] == "heartbeat_ack"


def test_session_is_closed_on_disconnect(fake_redis_client):
    token = make_token(sub=DEFAULT_TEST_USER_ID)
    session = _connected_session()
    p1, p2 = _patched(fake_redis_client, session)
    with p1, p2:
        with client.websocket_connect(f"{WS_URL}?token={token}") as ws:
            ws.receive_json()

    assert session.closed is True


# ---- end-to-end: two members, one broadcasts, the other receives ----------


@patch("app.websocket.handlers.trip_service.get_trip_by_id")
@patch("app.websocket.handlers.location_service.record_location")
def test_two_connected_members_location_update_is_broadcast(mock_record, mock_get_trip):
    """The full stack, both real pieces exercised together: two live
    WebSocket connections (via the app's real, shared ConnectionManager),
    one Redis "server," one publishes a location_update, the other
    receives it via Pub/Sub — not a direct in-process call.

    TestClient runs each nested websocket_connect() on its own event
    loop, so (unlike production, where one Uvicorn worker has exactly one
    loop for every connection) a single shared client instance's
    connection-pool lock would end up bound to the wrong loop. fakeredis's
    `server=` lets each connection get its own client while all of them
    still read/write the same underlying fake data — the correct way to
    simulate "one Redis, multiple independent client connections" here."""
    from datetime import datetime, timezone

    user_a = DEFAULT_TEST_USER_ID
    user_b = "22222222-2222-2222-2222-222222222222"
    token_a = make_token(sub=user_a)
    token_b = make_token(sub=user_b)

    mock_get_trip.return_value = make_trip(status=TripStatus.ACTIVE)
    mock_record.return_value = SimpleNamespace(
        latitude=22.7196, longitude=75.8577, accuracy=None, speed=None, heading=None,
        recorded_at=datetime.now(timezone.utc),
    )

    # Both users resolve as active members regardless of which one is
    # asking — good enough for exercising the broadcast path itself.
    session = FakeSession(trip=make_trip(status=TripStatus.ACTIVE), member=make_member(), member_rows=[])
    shared_server = fakeredis.FakeServer()
    p1 = patch(
        "app.api.websocket.get_redis",
        side_effect=lambda: fakeredis.FakeAsyncRedis(server=shared_server, decode_responses=True),
    )
    p2 = patch("app.api.websocket.SessionLocal", return_value=session)

    with p1, p2:
        with client.websocket_connect(f"{WS_URL}?token={token_a}") as ws_a:
            ws_a.receive_json()  # trip_state
            with client.websocket_connect(f"{WS_URL}?token={token_b}") as ws_b:
                ws_b.receive_json()  # trip_state

                ws_a.send_json({"type": "location_update", "data": {"latitude": 22.7196, "longitude": 75.8577}})

                # Both sockets also carry presence_update traffic (A is
                # subscribed to the same channel, so B's own connect
                # reaches it) — assert on the frame each side cares about
                # rather than a brittle exact ordering.
                ack = _receive_until(ws_a, "location_ack")
                assert ack["data"]["accepted"] is True

                broadcast = _receive_until(ws_b, "location_update")
                assert broadcast["data"]["user_id"] == user_a


# ---- Phase 11: connection-limit-per-user, message flooding -----------------


def test_exceeding_max_connections_per_user_is_rejected(monkeypatch):
    """A user's Nth+1 simultaneous connection for the same trip is
    rejected outright (not silently closing an older one — see the
    policy note in app/api/websocket.py) once MAX_WS_CONNECTIONS_PER_USER
    is reached. Needs the same fakeredis `server=` sharing trick as the
    two-different-users test above, since each nested websocket_connect()
    runs on its own event loop."""
    monkeypatch.setattr(settings, "MAX_WS_CONNECTIONS_PER_USER", 1)
    token = make_token(sub=DEFAULT_TEST_USER_ID)
    session = _connected_session()
    shared_server = fakeredis.FakeServer()
    p1 = patch(
        "app.api.websocket.get_redis",
        side_effect=lambda: fakeredis.FakeAsyncRedis(server=shared_server, decode_responses=True),
    )
    p2 = patch("app.api.websocket.SessionLocal", return_value=session)

    with p1, p2:
        with client.websocket_connect(f"{WS_URL}?token={token}") as ws1:
            ws1.receive_json()  # trip_state snapshot — first connection fully established

            with client.websocket_connect(f"{WS_URL}?token={token}") as ws2:
                error = ws2.receive_json()
                assert error["type"] == "error"
                assert error["data"]["code"] == "RATE_LIMITED"
                with pytest.raises(WebSocketDisconnect):
                    ws2.receive_json()

            # The first connection is untouched — rejecting the new one
            # never disturbed it.
            ws1.send_json({"type": "heartbeat"})
            assert ws1.receive_json()["type"] == "heartbeat_ack"


def test_message_flood_disconnects_after_threshold(fake_redis_client, monkeypatch):
    """A client blowing well past WEBSOCKET_MESSAGES_PER_SECOND on every
    single message gets disconnected outright after
    WEBSOCKET_FLOOD_DISCONNECT_THRESHOLD consecutive rate-limited
    messages — not just throttled forever."""
    # 0: every single message is rejected (WindowRateLimiter's max_per_second
    # is 0, so even the first message in a window fails), making this
    # deterministic rather than racing real wall-clock timing.
    monkeypatch.setattr(settings, "WEBSOCKET_MESSAGES_PER_SECOND", 0)
    monkeypatch.setattr(settings, "WEBSOCKET_FLOOD_DISCONNECT_THRESHOLD", 3)
    token = make_token(sub=DEFAULT_TEST_USER_ID)
    p1, p2 = _patched(fake_redis_client, _connected_session())
    with p1, p2:
        with client.websocket_connect(f"{WS_URL}?token={token}") as ws:
            ws.receive_json()  # trip_state snapshot

            for _ in range(3):
                ws.send_json({"type": "heartbeat"})
                msg = ws.receive_json()
                assert msg["type"] == "error"
                assert msg["data"]["code"] == "RATE_LIMITED"

            with pytest.raises(WebSocketDisconnect):
                ws.send_json({"type": "heartbeat"})
                ws.receive_json()


def test_single_burst_within_window_is_not_flagged_as_flooding(fake_redis_client):
    """A quick, small burst of a couple of different message types must
    not itself be treated as flooding — WindowRateLimiter allows up to
    WEBSOCKET_MESSAGES_PER_SECOND messages within the same second however
    they're spaced (see app/websocket/handlers.py); only sustained
    excess trips it."""
    token = make_token(sub=DEFAULT_TEST_USER_ID)
    p1, p2 = _patched(fake_redis_client, _connected_session())
    with p1, p2:
        with client.websocket_connect(f"{WS_URL}?token={token}") as ws:
            ws.receive_json()  # trip_state snapshot
            ws.send_json({"type": "heartbeat"})
            assert ws.receive_json()["type"] == "heartbeat_ack"
            ws.send_json({"type": "heartbeat"})
            assert ws.receive_json()["type"] == "heartbeat_ack"


# ---- regression: existing suites unaffected --------------------------------


def test_health_endpoint_still_works():
    response = client.get(f"{settings.API_V1_STR}/health")
    assert response.status_code == 200
