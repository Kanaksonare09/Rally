"""
Live (Redis-backed) trip state: current location per user + the set of
users who have one. This is deliberately NOT the historical record —
that's location_history in Postgres (see app/services/location_service.py).
Nothing here is ever treated as durable; every write here has (or is
covered by) a TTL, and losing it entirely just means live tracking
resets, not data loss.
"""

import json
import uuid
from typing import Any, Dict, List, Optional

from redis.asyncio import Redis

from app.core.config import settings
from app.core.redis_keys import live_location_key, presence_key, trip_users_key


def _serialize_location(
    user_id: uuid.UUID,
    trip_id: uuid.UUID,
    latitude: float,
    longitude: float,
    accuracy: Optional[float],
    speed: Optional[float],
    heading: Optional[float],
    recorded_at: str,
    updated_at: str,
) -> str:
    return json.dumps(
        {
            "user_id": str(user_id),
            "trip_id": str(trip_id),
            "latitude": latitude,
            "longitude": longitude,
            "accuracy": accuracy,
            "speed": speed,
            "heading": heading,
            "recorded_at": recorded_at,
            "updated_at": updated_at,
        }
    )


async def set_live_location(
    redis: Redis,
    trip_id: uuid.UUID,
    user_id: uuid.UUID,
    *,
    latitude: float,
    longitude: float,
    accuracy: Optional[float],
    speed: Optional[float],
    heading: Optional[float],
    recorded_at: str,
    updated_at: str,
    ttl_seconds: Optional[int] = None,
) -> None:
    """Overwrites the user's current location and (re)sets its TTL — every
    update refreshes the clock, so an actively-tracking user never goes
    stale mid-trip. Also adds the user to the trip's live-users set (that
    set itself doesn't expire; it's cleaned up explicitly on trip end, see
    clear_trip_state())."""
    ttl = ttl_seconds if ttl_seconds is not None else settings.LIVE_LOCATION_TTL_SECONDS
    payload = _serialize_location(
        user_id, trip_id, latitude, longitude, accuracy, speed, heading, recorded_at, updated_at
    )
    async with redis.pipeline(transaction=True) as pipe:
        pipe.set(live_location_key(trip_id, user_id), payload, ex=ttl)
        pipe.sadd(trip_users_key(trip_id), str(user_id))
        await pipe.execute()


async def get_live_location(redis: Redis, trip_id: uuid.UUID, user_id: uuid.UUID) -> Optional[Dict[str, Any]]:
    raw = await redis.get(live_location_key(trip_id, user_id))
    if raw is None:
        return None
    return json.loads(raw)


async def get_live_locations(redis: Redis, trip_id: uuid.UUID, user_ids: List[uuid.UUID]) -> Dict[str, Dict[str, Any]]:
    """Bulk read for building a trip_state snapshot — one round trip
    (MGET) instead of one GET per member."""
    if not user_ids:
        return {}
    keys = [live_location_key(trip_id, uid) for uid in user_ids]
    values = await redis.mget(keys)
    result: Dict[str, Dict[str, Any]] = {}
    for user_id, raw in zip(user_ids, values):
        if raw is not None:
            result[str(user_id)] = json.loads(raw)
    return result


async def get_active_user_ids(redis: Redis, trip_id: uuid.UUID) -> set:
    return await redis.smembers(trip_users_key(trip_id))


async def clear_trip_state(redis: Redis, trip_id: uuid.UUID, user_ids: List[uuid.UUID]) -> None:
    """Called when a trip ends (COMPLETED/CANCELLED). Removes every piece
    of live state for the trip — locations, presence, the active-users
    set. Does not touch location_history; that's Postgres's job and stays
    untouched here."""
    keys = [trip_users_key(trip_id)]
    for uid in user_ids:
        keys.append(live_location_key(trip_id, uid))
        keys.append(presence_key(trip_id, uid))
    if keys:
        await redis.delete(*keys)
