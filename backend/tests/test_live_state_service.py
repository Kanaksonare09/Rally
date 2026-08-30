"""
Redis-backed live state, tested against fakeredis (see tests/conftest.py's
fake_redis fixture) — no real Redis server required.
"""

import uuid
from datetime import datetime, timezone

import pytest

from app.core.redis_keys import live_location_key, presence_key, trip_users_key
from app.services import live_state_service

TRIP_ID = uuid.uuid4()
USER_ID = uuid.uuid4()
NOW_ISO = datetime.now(timezone.utc).isoformat()


async def _set_location(redis, ttl_seconds=None):
    await live_state_service.set_live_location(
        redis,
        TRIP_ID,
        USER_ID,
        latitude=22.7196,
        longitude=75.8577,
        accuracy=8.5,
        speed=12.4,
        heading=180.0,
        recorded_at=NOW_ISO,
        updated_at=NOW_ISO,
        ttl_seconds=ttl_seconds,
    )


async def test_live_location_can_be_stored_and_read_back(fake_redis):
    await _set_location(fake_redis)
    location = await live_state_service.get_live_location(fake_redis, TRIP_ID, USER_ID)

    assert location is not None
    assert location["user_id"] == str(USER_ID)
    assert location["trip_id"] == str(TRIP_ID)
    assert location["latitude"] == 22.7196
    assert location["longitude"] == 75.8577
    assert location["accuracy"] == 8.5
    assert location["speed"] == 12.4
    assert location["heading"] == 180.0


async def test_missing_live_location_returns_none(fake_redis):
    assert await live_state_service.get_live_location(fake_redis, TRIP_ID, uuid.uuid4()) is None


async def test_live_location_ttl_is_applied(fake_redis):
    await _set_location(fake_redis, ttl_seconds=45)
    ttl = await fake_redis.ttl(live_location_key(TRIP_ID, USER_ID))
    assert 0 < ttl <= 45


async def test_live_location_defaults_to_configured_ttl(fake_redis, monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, "LIVE_LOCATION_TTL_SECONDS", 30)
    await _set_location(fake_redis)  # no explicit ttl_seconds -> uses settings
    ttl = await fake_redis.ttl(live_location_key(TRIP_ID, USER_ID))
    assert 0 < ttl <= 30


async def test_setting_location_adds_user_to_trip_users_set(fake_redis):
    await _set_location(fake_redis)
    members = await fake_redis.smembers(trip_users_key(TRIP_ID))
    assert str(USER_ID) in members


async def test_get_active_user_ids_reflects_the_set(fake_redis):
    await _set_location(fake_redis)
    active = await live_state_service.get_active_user_ids(fake_redis, TRIP_ID)
    assert str(USER_ID) in active


async def test_get_live_locations_bulk_read(fake_redis):
    user_a, user_b, user_c = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    await live_state_service.set_live_location(
        fake_redis, TRIP_ID, user_a, latitude=1, longitude=1, accuracy=None, speed=None, heading=None,
        recorded_at=NOW_ISO, updated_at=NOW_ISO,
    )
    await live_state_service.set_live_location(
        fake_redis, TRIP_ID, user_b, latitude=2, longitude=2, accuracy=None, speed=None, heading=None,
        recorded_at=NOW_ISO, updated_at=NOW_ISO,
    )
    # user_c never sent a location — should be absent from the result, not an error.
    result = await live_state_service.get_live_locations(fake_redis, TRIP_ID, [user_a, user_b, user_c])

    assert set(result.keys()) == {str(user_a), str(user_b)}
    assert result[str(user_a)]["latitude"] == 1
    assert result[str(user_b)]["latitude"] == 2


async def test_get_live_locations_with_empty_list_returns_empty_dict(fake_redis):
    assert await live_state_service.get_live_locations(fake_redis, TRIP_ID, []) == {}


async def test_clear_trip_state_removes_locations_presence_and_active_set(fake_redis):
    from app.services import presence_service

    await _set_location(fake_redis)
    await presence_service.mark_online(fake_redis, TRIP_ID, USER_ID)

    await live_state_service.clear_trip_state(fake_redis, TRIP_ID, [USER_ID])

    assert await fake_redis.get(live_location_key(TRIP_ID, USER_ID)) is None
    assert await fake_redis.exists(presence_key(TRIP_ID, USER_ID)) == 0
    assert await fake_redis.exists(trip_users_key(TRIP_ID)) == 0


async def test_clear_trip_state_does_not_touch_other_trips(fake_redis):
    other_trip = uuid.uuid4()
    await _set_location(fake_redis)
    await live_state_service.set_live_location(
        fake_redis, other_trip, USER_ID, latitude=9, longitude=9, accuracy=None, speed=None, heading=None,
        recorded_at=NOW_ISO, updated_at=NOW_ISO,
    )

    await live_state_service.clear_trip_state(fake_redis, TRIP_ID, [USER_ID])

    assert await live_state_service.get_live_location(fake_redis, other_trip, USER_ID) is not None
