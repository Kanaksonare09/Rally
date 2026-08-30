import redis.asyncio as redis
from typing import AsyncGenerator
from fastapi import Request

# Global connection pool initialized on startup
redis_client: redis.Redis = None  # type: ignore

async def init_redis(redis_url: str) -> None:
    global redis_client
    redis_client = redis.from_url(redis_url, decode_responses=True)

async def close_redis() -> None:
    global redis_client
    if redis_client:
        await redis_client.aclose()

async def get_redis() -> AsyncGenerator[redis.Redis, None]:
    """Dependency for getting the Redis client."""
    yield redis_client
