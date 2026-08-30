import uuid

from app.core.redis_keys import live_location_key, presence_key, trip_channel, trip_users_key

TRIP_ID = uuid.uuid4()
USER_ID = uuid.uuid4()


def test_live_location_key_format():
    assert live_location_key(TRIP_ID, USER_ID) == f"trip:{TRIP_ID}:user:{USER_ID}:location"


def test_trip_users_key_format():
    assert trip_users_key(TRIP_ID) == f"trip:{TRIP_ID}:users"


def test_presence_key_format():
    assert presence_key(TRIP_ID, USER_ID) == f"trip:{TRIP_ID}:presence:{USER_ID}"


def test_trip_channel_format():
    assert trip_channel(TRIP_ID) == f"trip:{TRIP_ID}:events"


def test_keys_are_unique_per_trip_and_user():
    other_trip, other_user = uuid.uuid4(), uuid.uuid4()
    assert live_location_key(TRIP_ID, USER_ID) != live_location_key(other_trip, USER_ID)
    assert live_location_key(TRIP_ID, USER_ID) != live_location_key(TRIP_ID, other_user)
    assert presence_key(TRIP_ID, USER_ID) != presence_key(other_trip, USER_ID)
    assert trip_channel(TRIP_ID) != trip_channel(other_trip)


def test_keys_accept_plain_strings_too():
    """Callers sometimes have str(uuid) already on hand (e.g. from a
    WebSocket URL path param) — keys must be identical either way."""
    assert live_location_key(str(TRIP_ID), str(USER_ID)) == live_location_key(TRIP_ID, USER_ID)
