"""
Message-handling logic (parse -> validate -> persist -> live-state ->
broadcast -> ack), tested against fakeredis for the Redis half and mocked
service calls for the DB half (no live database — see backend README,
same pattern as test_trips_api.py / test_locations_api.py).
"""

import json
import uuid
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from app.core.errors import AppHTTPException
from app.websocket.auth import TripConnectionContext
from app.websocket.handlers import RateLimiter, TripActiveFlag, handle_client_message
from app.models.enums import MemberRole

TRIP_ID = uuid.uuid4()
GROUP_ID = uuid.uuid4()
USER_ID = uuid.uuid4()


def make_ctx() -> TripConnectionContext:
    return TripConnectionContext(user_id=USER_ID, trip_id=TRIP_ID, group_id=GROUP_ID, role=MemberRole.MEMBER)


def make_location_row(**overrides):
    row = SimpleNamespace(
        id=uuid.uuid4(),
        trip_id=TRIP_ID,
        group_id=GROUP_ID,
        user_id=USER_ID,
        latitude=22.7196,
        longitude=75.8577,
        accuracy=8.5,
        speed=12.4,
        heading=180.0,
        recorded_at=datetime.now(timezone.utc),
    )
    for k, v in overrides.items():
        setattr(row, k, v)
    return row


async def _handle(raw, redis, ctx=None, rate_limiter=None, trip_active=None):
    return await handle_client_message(
        raw=raw if isinstance(raw, str) else json.dumps(raw),
        db=object(),  # never touched directly by handle_client_message itself
        redis=redis,
        ctx=ctx or make_ctx(),
        rate_limiter=rate_limiter or RateLimiter(max_per_second=1000),
        trip_active=trip_active or TripActiveFlag(active=True),
    )


# ---- message parsing -----------------------------------------------------


async def test_invalid_json_returns_invalid_message_error(fake_redis):
    response = await _handle("not json at all", fake_redis)
    assert response["type"] == "error"
    assert response["data"]["code"] == "INVALID_MESSAGE"


async def test_missing_type_field_returns_invalid_message_error(fake_redis):
    response = await _handle({"data": {}}, fake_redis)
    assert response["data"]["code"] == "INVALID_MESSAGE"


async def test_unknown_message_type_returns_invalid_message_error(fake_redis):
    response = await _handle({"type": "not_a_real_type"}, fake_redis)
    assert response["data"]["code"] == "INVALID_MESSAGE"


async def test_oversized_message_is_rejected(fake_redis, monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, "WS_MAX_MESSAGE_BYTES", 32)
    response = await _handle({"type": "location_update", "data": {"latitude": 1, "longitude": 1, "note": "x" * 100}}, fake_redis)
    assert response["data"]["code"] == "INVALID_MESSAGE"


# ---- heartbeat -------------------------------------------------------------


async def test_heartbeat_returns_heartbeat_ack(fake_redis):
    response = await _handle({"type": "heartbeat"}, fake_redis)
    assert response["type"] == "heartbeat_ack"


async def test_heartbeat_marks_presence_online(fake_redis):
    from app.services import presence_service

    ctx = make_ctx()
    await _handle({"type": "heartbeat"}, fake_redis, ctx=ctx)
    assert await presence_service.is_online(fake_redis, ctx.trip_id, ctx.user_id) is True


# ---- location_update: validation ------------------------------------------


@pytest.mark.parametrize(
    "data",
    [
        {"latitude": 91, "longitude": 0},
        {"latitude": -91, "longitude": 0},
        {"latitude": 0, "longitude": 181},
        {"latitude": 0, "longitude": -181},
        {"latitude": 0, "longitude": 0, "accuracy": -1},
        {"latitude": 0, "longitude": 0, "speed": -1},
        {"latitude": 0, "longitude": 0, "heading": 360},
        {"latitude": 0, "longitude": 0, "heading": -1},
    ],
)
async def test_invalid_location_fields_are_rejected(fake_redis, data):
    response = await _handle({"type": "location_update", "data": data}, fake_redis)
    assert response["type"] == "error"
    assert response["data"]["code"] == "INVALID_LOCATION"


async def test_missing_required_fields_returns_invalid_location(fake_redis):
    response = await _handle({"type": "location_update", "data": {}}, fake_redis)
    assert response["data"]["code"] == "INVALID_LOCATION"


# ---- location_update: trusted identity -------------------------------------


@patch("app.websocket.handlers.trip_service.get_trip_by_id")
@patch("app.websocket.handlers.location_service.record_location")
async def test_client_cannot_impersonate_another_user_or_trip(mock_record, mock_get_trip, fake_redis):
    """user_id/trip_id/group_id are never read from the client message —
    only from the authenticated connection context."""
    mock_get_trip.return_value = SimpleNamespace(id=TRIP_ID, group_id=GROUP_ID)
    mock_record.return_value = make_location_row()
    ctx = make_ctx()

    smuggled = {
        "latitude": 1,
        "longitude": 1,
        "user_id": str(uuid.uuid4()),
        "trip_id": str(uuid.uuid4()),
        "group_id": str(uuid.uuid4()),
    }
    await _handle({"type": "location_update", "data": smuggled}, fake_redis, ctx=ctx)

    # record_location was called with ctx's own ids, not anything from the message.
    called_user_id = mock_record.call_args.args[2]
    assert called_user_id == ctx.user_id
    mock_get_trip.assert_called_once_with(mock_get_trip.call_args.args[0], ctx.trip_id)


# ---- location_update: happy path -------------------------------------------


@patch("app.websocket.handlers.trip_service.get_trip_by_id")
@patch("app.websocket.handlers.location_service.record_location")
async def test_valid_location_update_is_persisted_and_acked(mock_record, mock_get_trip, fake_redis):
    mock_get_trip.return_value = SimpleNamespace(id=TRIP_ID, group_id=GROUP_ID)
    mock_record.return_value = make_location_row()

    response = await _handle(
        {"type": "location_update", "data": {"latitude": 22.7196, "longitude": 75.8577, "speed": 12.4}},
        fake_redis,
    )

    assert response["type"] == "location_ack"
    assert response["data"]["accepted"] is True
    mock_record.assert_called_once()


@patch("app.websocket.handlers.trip_service.get_trip_by_id")
@patch("app.websocket.handlers.location_service.record_location")
async def test_valid_location_update_is_stored_in_redis(mock_record, mock_get_trip, fake_redis):
    from app.services import live_state_service

    mock_get_trip.return_value = SimpleNamespace(id=TRIP_ID, group_id=GROUP_ID)
    mock_record.return_value = make_location_row(latitude=10.0, longitude=20.0)
    ctx = make_ctx()

    await _handle({"type": "location_update", "data": {"latitude": 10.0, "longitude": 20.0}}, fake_redis, ctx=ctx)

    live = await live_state_service.get_live_location(fake_redis, ctx.trip_id, ctx.user_id)
    assert live is not None
    assert live["latitude"] == 10.0
    assert live["longitude"] == 20.0


@patch("app.websocket.handlers.trip_service.get_trip_by_id")
@patch("app.websocket.handlers.location_service.record_location")
async def test_valid_location_update_marks_presence_online(mock_record, mock_get_trip, fake_redis):
    from app.services import presence_service

    mock_get_trip.return_value = SimpleNamespace(id=TRIP_ID, group_id=GROUP_ID)
    mock_record.return_value = make_location_row()
    ctx = make_ctx()

    await _handle({"type": "location_update", "data": {"latitude": 1, "longitude": 1}}, fake_redis, ctx=ctx)

    assert await presence_service.is_online(fake_redis, ctx.trip_id, ctx.user_id) is True


@patch("app.websocket.handlers.trip_service.get_trip_by_id")
@patch("app.websocket.handlers.location_service.record_location")
async def test_valid_location_update_is_broadcast_to_other_members(mock_record, mock_get_trip, fake_redis):
    import asyncio

    from app.websocket.manager import ConnectionManager

    mock_get_trip.return_value = SimpleNamespace(id=TRIP_ID, group_id=GROUP_ID)
    mock_record.return_value = make_location_row()
    ctx = make_ctx()

    manager = ConnectionManager()

    class _FakeWS:
        def __init__(self):
            self.sent = []

        async def send_text(self, text):
            self.sent.append(json.loads(text))

    other_ws = _FakeWS()
    other_user = str(uuid.uuid4())
    await manager.connect(fake_redis, str(TRIP_ID), other_user, other_ws)

    with patch("app.websocket.manager.manager", manager):
        await _handle({"type": "location_update", "data": {"latitude": 1, "longitude": 1}}, fake_redis, ctx=ctx)

    for _ in range(20):
        if other_ws.sent:
            break
        await asyncio.sleep(0.05)

    assert len(other_ws.sent) == 1
    assert other_ws.sent[0]["type"] == "location_update"
    assert other_ws.sent[0]["data"]["user_id"] == str(ctx.user_id)


# ---- location_update: trip-state / rate limiting / failure handling --------


async def test_location_update_rejected_when_trip_already_marked_inactive(fake_redis):
    response = await _handle(
        {"type": "location_update", "data": {"latitude": 1, "longitude": 1}},
        fake_redis,
        trip_active=TripActiveFlag(active=False),
    )
    assert response["type"] == "error"
    assert response["data"]["code"] == "TRIP_NOT_ACTIVE"


async def test_rate_limited_client_gets_rate_limited_error(fake_redis):
    class _NeverAllow:
        def allow(self):
            return False

    response = await _handle(
        {"type": "location_update", "data": {"latitude": 1, "longitude": 1}},
        fake_redis,
        rate_limiter=_NeverAllow(),
    )
    assert response["data"]["code"] == "RATE_LIMITED"


@patch("app.websocket.handlers.trip_service.get_trip_by_id")
@patch("app.websocket.handlers.location_service.record_location")
async def test_invalid_trip_state_flips_the_cached_trip_active_flag(mock_record, mock_get_trip, fake_redis):
    mock_get_trip.return_value = SimpleNamespace(id=TRIP_ID, group_id=GROUP_ID)
    mock_record.side_effect = AppHTTPException(status_code=409, code="INVALID_TRIP_STATE", detail="not active")
    trip_active = TripActiveFlag(active=True)

    response = await _handle(
        {"type": "location_update", "data": {"latitude": 1, "longitude": 1}}, fake_redis, trip_active=trip_active
    )

    assert response["data"]["code"] == "TRIP_NOT_ACTIVE"
    assert trip_active.active is False


@patch("app.websocket.handlers.trip_service.get_trip_by_id")
@patch("app.websocket.handlers.location_service.record_location")
async def test_invalid_timestamp_maps_to_invalid_location_error(mock_record, mock_get_trip, fake_redis):
    mock_get_trip.return_value = SimpleNamespace(id=TRIP_ID, group_id=GROUP_ID)
    mock_record.side_effect = AppHTTPException(status_code=400, code="INVALID_TIMESTAMP", detail="too far future")

    response = await _handle({"type": "location_update", "data": {"latitude": 1, "longitude": 1}}, fake_redis)

    assert response["data"]["code"] == "INVALID_LOCATION"


@patch("app.websocket.handlers.trip_service.get_trip_by_id")
@patch("app.websocket.handlers.location_service.record_location")
async def test_storage_failure_never_falsely_claims_permanent_storage(mock_record, mock_get_trip, fake_redis):
    """A real persistence failure (DB unreachable, etc.) must come back as
    a rejected ack, never as accepted."""
    mock_get_trip.return_value = SimpleNamespace(id=TRIP_ID, group_id=GROUP_ID)
    mock_record.side_effect = RuntimeError("connection refused")

    response = await _handle({"type": "location_update", "data": {"latitude": 1, "longitude": 1}}, fake_redis)

    assert response["type"] == "location_ack"
    assert response["data"]["accepted"] is False
