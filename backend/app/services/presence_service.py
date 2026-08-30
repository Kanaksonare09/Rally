"""
Presence: is this user currently reachable on this trip's WebSocket?
Deliberately separate from live_state_service (location freshness) — a
user can be ONLINE with a 45-second-old GPS point, or briefly offline with
a perfectly fresh one. Don't conflate the two.

Presence is a pure TTL key: while `presence_key(trip_id, user_id)` exists,
the user is ONLINE; once it expires (no heartbeat/location for
PRESENCE_TTL_SECONDS), they're STALE/OFFLINE. Nothing here is persisted
to Postgres — presence resets to unknown on every restart, by design.
"""

import uuid
from typing import Dict, List, Optional

from redis.asyncio import Redis

from app.core.config import settings
from app.core.redis_keys import presence_key


async def mark_online(
    redis: Redis, trip_id: uuid.UUID, user_id: uuid.UUID, ttl_seconds: Optional[int] = None
) -> None:
    """Sets/refreshes the presence TTL. Safe to call on every heartbeat
    and every location_update — cheap single SETEX."""
    ttl = ttl_seconds if ttl_seconds is not None else settings.PRESENCE_TTL_SECONDS
    await redis.set(presence_key(trip_id, user_id), "1", ex=ttl)


async def is_online(redis: Redis, trip_id: uuid.UUID, user_id: uuid.UUID) -> bool:
    return await redis.exists(presence_key(trip_id, user_id)) > 0


async def get_online_status(redis: Redis, trip_id: uuid.UUID, user_ids: List[uuid.UUID]) -> Dict[str, bool]:
    """Bulk presence check for building a trip_state snapshot — one
    pipelined round trip instead of one EXISTS per member."""
    if not user_ids:
        return {}
    async with redis.pipeline(transaction=False) as pipe:
        for uid in user_ids:
            pipe.exists(presence_key(trip_id, uid))
        results = await pipe.execute()
    return {str(uid): bool(exists) for uid, exists in zip(user_ids, results)}


async def clear_presence(redis: Redis, trip_id: uuid.UUID, user_id: uuid.UUID) -> None:
    """Called on a clean disconnect (last connection for this user gone) —
    marks them offline immediately rather than waiting out the TTL."""
    await redis.delete(presence_key(trip_id, user_id))
