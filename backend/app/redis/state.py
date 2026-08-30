import json
import uuid
from datetime import datetime, timezone
from typing import Dict, List, Optional
import redis.asyncio as redis

# rally:group:{group_id}:members -> hash of user_id -> json
def _group_key(group_id: uuid.UUID | str) -> str:
    return f"rally:group:{group_id}:members"

async def set_member_state(
    redis_client: redis.Redis,
    group_id: uuid.UUID | str,
    user_id: uuid.UUID | str,
    state: dict
) -> None:
    """Store or update the current state of a member in the group."""
    # Convert any datetimes to ISO formats
    for k, v in state.items():
        if isinstance(v, datetime):
            state[k] = v.isoformat()
        elif isinstance(v, uuid.UUID):
            state[k] = str(v)
            
    await redis_client.hset(_group_key(group_id), str(user_id), json.dumps(state))

async def get_member_state(
    redis_client: redis.Redis,
    group_id: uuid.UUID | str,
    user_id: uuid.UUID | str,
) -> Optional[dict]:
    """Get the current state of a member."""
    raw = await redis_client.hget(_group_key(group_id), str(user_id))
    if not raw:
        return None
    return json.loads(raw)

async def get_group_live_state(
    redis_client: redis.Redis,
    group_id: uuid.UUID | str
) -> List[dict]:
    """Get the current state of all members in the group."""
    raw_states = await redis_client.hgetall(_group_key(group_id))
    return [json.loads(s) for s in raw_states.values()]

async def set_member_online(
    redis_client: redis.Redis,
    group_id: uuid.UUID | str,
    user_id: uuid.UUID | str,
) -> None:
    """Mark a member as online and update last_seen."""
    state = await get_member_state(redis_client, group_id, user_id) or {}
    state["user_id"] = str(user_id)
    state["connection_state"] = "ONLINE"
    state["last_seen"] = datetime.now(timezone.utc).isoformat()
    await set_member_state(redis_client, group_id, user_id, state)

async def set_member_offline(
    redis_client: redis.Redis,
    group_id: uuid.UUID | str,
    user_id: uuid.UUID | str,
) -> None:
    """Mark a member as offline and update last_seen."""
    state = await get_member_state(redis_client, group_id, user_id) or {}
    state["user_id"] = str(user_id)
    state["connection_state"] = "OFFLINE"
    state["last_seen"] = datetime.now(timezone.utc).isoformat()
    await set_member_state(redis_client, group_id, user_id, state)

