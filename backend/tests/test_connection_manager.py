"""
ConnectionManager tests use a fresh instance per test (not the module-level
`manager` singleton) for isolation, and fakeredis for the Pub/Sub
subscriber loop each connect() spins up.
"""

import asyncio
import json

import pytest

from app.websocket.manager import ConnectionManager, publish_event

TRIP_A = "trip-a"
TRIP_B = "trip-b"
USER_1 = "user-1"
USER_2 = "user-2"


class FakeWebSocket:
    def __init__(self):
        self.sent = []
        self.closed_with = None

    async def send_text(self, text: str) -> None:
        self.sent.append(json.loads(text))

    async def close(self, code: int = 1000) -> None:
        self.closed_with = code


@pytest.fixture
def manager():
    return ConnectionManager()


async def test_connect_reports_first_connection_for_new_user(manager, fake_redis):
    is_first = await manager.connect(fake_redis, TRIP_A, USER_1, FakeWebSocket())
    assert is_first is True


async def test_second_connection_for_same_user_is_not_first(manager, fake_redis):
    await manager.connect(fake_redis, TRIP_A, USER_1, FakeWebSocket())
    is_first = await manager.connect(fake_redis, TRIP_A, USER_1, FakeWebSocket())
    assert is_first is False


async def test_connection_count_tracks_multiple_devices_for_one_user(manager, fake_redis):
    ws_a, ws_b = FakeWebSocket(), FakeWebSocket()
    await manager.connect(fake_redis, TRIP_A, USER_1, ws_a)
    await manager.connect(fake_redis, TRIP_A, USER_1, ws_b)
    assert manager.connection_count(TRIP_A, USER_1) == 2


async def test_disconnect_one_of_two_devices_is_not_last(manager, fake_redis):
    ws_a, ws_b = FakeWebSocket(), FakeWebSocket()
    await manager.connect(fake_redis, TRIP_A, USER_1, ws_a)
    await manager.connect(fake_redis, TRIP_A, USER_1, ws_b)

    is_last = await manager.disconnect(TRIP_A, USER_1, ws_a)

    assert is_last is False
    assert manager.connection_count(TRIP_A, USER_1) == 1


async def test_disconnect_last_device_is_last(manager, fake_redis):
    ws = FakeWebSocket()
    await manager.connect(fake_redis, TRIP_A, USER_1, ws)

    is_last = await manager.disconnect(TRIP_A, USER_1, ws)

    assert is_last is True
    assert manager.connection_count(TRIP_A, USER_1) == 0


async def test_disconnect_for_unknown_trip_is_safe(manager):
    """Must not raise even if connect() was never called for this trip."""
    is_last = await manager.disconnect("never-connected-trip", USER_1, FakeWebSocket())
    assert is_last is True


async def test_send_to_user_only_reaches_that_users_connections(manager, fake_redis):
    ws_1, ws_2 = FakeWebSocket(), FakeWebSocket()
    await manager.connect(fake_redis, TRIP_A, USER_1, ws_1)
    await manager.connect(fake_redis, TRIP_A, USER_2, ws_2)

    await manager.send_to_user(TRIP_A, USER_1, {"type": "location_ack", "data": {}})

    assert ws_1.sent == [{"type": "location_ack", "data": {}}]
    assert ws_2.sent == []


async def test_broadcast_to_trip_reaches_all_local_connections(manager, fake_redis):
    ws_1, ws_2 = FakeWebSocket(), FakeWebSocket()
    await manager.connect(fake_redis, TRIP_A, USER_1, ws_1)
    await manager.connect(fake_redis, TRIP_A, USER_2, ws_2)

    await manager.broadcast_to_trip(TRIP_A, {"type": "presence_update", "data": {}})

    assert ws_1.sent == [{"type": "presence_update", "data": {}}]
    assert ws_2.sent == [{"type": "presence_update", "data": {}}]


async def test_broadcast_to_trip_excludes_given_user(manager, fake_redis):
    ws_1, ws_2 = FakeWebSocket(), FakeWebSocket()
    await manager.connect(fake_redis, TRIP_A, USER_1, ws_1)
    await manager.connect(fake_redis, TRIP_A, USER_2, ws_2)

    await manager.broadcast_to_trip(TRIP_A, {"type": "location_update", "data": {}}, exclude_user_id=USER_1)

    assert ws_1.sent == []
    assert ws_2.sent == [{"type": "location_update", "data": {}}]


async def test_broadcast_does_not_cross_trips(manager, fake_redis):
    ws_a, ws_b = FakeWebSocket(), FakeWebSocket()
    await manager.connect(fake_redis, TRIP_A, USER_1, ws_a)
    await manager.connect(fake_redis, TRIP_B, USER_1, ws_b)

    await manager.broadcast_to_trip(TRIP_A, {"type": "heartbeat_ack", "data": {}})

    assert ws_a.sent == [{"type": "heartbeat_ack", "data": {}}]
    assert ws_b.sent == []


async def test_publish_event_reaches_local_connections_via_subscriber_loop(manager, fake_redis):
    """The cross-instance path: publish_event() PUBLISHes to Redis; this
    process's own subscriber task (started by connect()) picks it back up
    and forwards it locally — proving Pub/Sub, not a direct method call,
    is what's actually wiring broadcasts together."""
    ws = FakeWebSocket()
    await manager.connect(fake_redis, TRIP_A, USER_1, ws)
    await asyncio.sleep(0.05)

    await publish_event(fake_redis, TRIP_A, {"type": "location_update", "data": {"user_id": USER_2}})

    for _ in range(20):
        if ws.sent:
            break
        await asyncio.sleep(0.05)

    assert ws.sent == [{"type": "location_update", "data": {"user_id": USER_2}}]


async def test_publish_event_exclude_user_id_is_not_leaked_to_client(manager, fake_redis):
    """exclude_user_id is pub/sub transport metadata only — it must never
    appear inside the message a client actually receives."""
    ws = FakeWebSocket()
    await manager.connect(fake_redis, TRIP_A, USER_2, ws)
    await asyncio.sleep(0.05)

    await publish_event(fake_redis, TRIP_A, {"type": "location_update", "data": {}}, exclude_user_id=USER_1)

    for _ in range(20):
        if ws.sent:
            break
        await asyncio.sleep(0.05)

    assert ws.sent == [{"type": "location_update", "data": {}}]


async def test_close_trip_connections_closes_every_local_socket(manager, fake_redis):
    ws_1, ws_2 = FakeWebSocket(), FakeWebSocket()
    await manager.connect(fake_redis, TRIP_A, USER_1, ws_1)
    await manager.connect(fake_redis, TRIP_A, USER_2, ws_2)

    await manager.close_trip_connections(TRIP_A, code=4000)

    assert ws_1.closed_with == 4000
    assert ws_2.closed_with == 4000
    assert manager.connection_count(TRIP_A, USER_1) == 0
