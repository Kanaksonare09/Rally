import uuid

from app.core.redis_keys import presence_key
from app.services import presence_service

TRIP_ID = uuid.uuid4()
USER_ID = uuid.uuid4()


async def test_mark_online_then_is_online_true(fake_redis):
    await presence_service.mark_online(fake_redis, TRIP_ID, USER_ID)
    assert await presence_service.is_online(fake_redis, TRIP_ID, USER_ID) is True


async def test_user_with_no_presence_key_is_not_online(fake_redis):
    assert await presence_service.is_online(fake_redis, TRIP_ID, uuid.uuid4()) is False


async def test_presence_ttl_is_applied(fake_redis):
    await presence_service.mark_online(fake_redis, TRIP_ID, USER_ID, ttl_seconds=20)
    ttl = await fake_redis.ttl(presence_key(TRIP_ID, USER_ID))
    assert 0 < ttl <= 20


async def test_presence_defaults_to_configured_ttl(fake_redis, monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, "PRESENCE_TTL_SECONDS", 15)
    await presence_service.mark_online(fake_redis, TRIP_ID, USER_ID)
    ttl = await fake_redis.ttl(presence_key(TRIP_ID, USER_ID))
    assert 0 < ttl <= 15


async def test_clear_presence_marks_user_offline_immediately():
    import fakeredis

    redis = fakeredis.FakeAsyncRedis(decode_responses=True)
    await presence_service.mark_online(redis, TRIP_ID, USER_ID, ttl_seconds=60)
    assert await presence_service.is_online(redis, TRIP_ID, USER_ID) is True

    await presence_service.clear_presence(redis, TRIP_ID, USER_ID)

    assert await presence_service.is_online(redis, TRIP_ID, USER_ID) is False


async def test_get_online_status_bulk_check(fake_redis):
    online_user, offline_user = uuid.uuid4(), uuid.uuid4()
    await presence_service.mark_online(fake_redis, TRIP_ID, online_user)

    result = await presence_service.get_online_status(fake_redis, TRIP_ID, [online_user, offline_user])

    assert result[str(online_user)] is True
    assert result[str(offline_user)] is False


async def test_get_online_status_with_empty_list_returns_empty_dict(fake_redis):
    assert await presence_service.get_online_status(fake_redis, TRIP_ID, []) == {}
