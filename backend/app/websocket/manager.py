"""
Local (per-process) WebSocket connection registry, plus the Redis Pub/Sub
fan-in that makes broadcasts work across multiple FastAPI
instances/workers. A single process can hold many connections for the
same trip (multiple members, multiple tabs/devices per member) — this
class is the one place that state lives, instead of a loose global dict
scattered through the app.

Cross-instance broadcast: event *producers* (the location_update handler,
trip-end triggers) never call broadcast_to_trip() directly — they call
publish_event(), which PUBLISHes to Redis. Every instance with at least
one local connection for a trip runs one background subscriber task for
that trip's channel (started on the first local connection, stopped on
the last) and forwards whatever it receives to its own local connections.
That's "one Redis connection per trip channel," not one per message and
not one per WebSocket.
"""

import asyncio
import json
import logging
from typing import Dict, Optional, Set

from fastapi import WebSocket
from redis.asyncio import Redis

from app.core.redis_keys import trip_channel

logger = logging.getLogger("rally.websocket")


class ConnectionManager:
    def __init__(self) -> None:
        # trip_id -> user_id -> set of live WebSocket connections
        self._connections: Dict[str, Dict[str, Set[WebSocket]]] = {}
        # trip_id -> background task subscribing to that trip's Redis channel
        self._subscriber_tasks: Dict[str, asyncio.Task] = {}
        self._lock = asyncio.Lock()

    async def connect(self, redis: Redis, trip_id: str, user_id: str, websocket: WebSocket) -> bool:
        """Registers the connection. Returns True if this is the user's
        first live connection for this trip — callers use that to decide
        whether to publish a presence ONLINE event (a second tab/device
        connecting shouldn't re-announce someone who's already online)."""
        async with self._lock:
            trip_conns = self._connections.setdefault(trip_id, {})
            user_conns = trip_conns.setdefault(user_id, set())
            is_first_for_user = len(user_conns) == 0
            user_conns.add(websocket)

            if trip_id not in self._subscriber_tasks:
                self._subscriber_tasks[trip_id] = asyncio.create_task(self._subscribe_loop(redis, trip_id))

        return is_first_for_user

    async def disconnect(self, trip_id: str, user_id: str, websocket: WebSocket) -> bool:
        """Unregisters the connection. Returns True if the user has no
        other live connections left for this trip (i.e. they should now
        be announced OFFLINE)."""
        is_last_for_user = True
        stop_subscriber = False
        async with self._lock:
            trip_conns = self._connections.get(trip_id)
            if trip_conns is None:
                return True
            user_conns = trip_conns.get(user_id)
            if user_conns is not None:
                user_conns.discard(websocket)
                if user_conns:
                    is_last_for_user = False
                else:
                    trip_conns.pop(user_id, None)

            if not trip_conns:
                self._connections.pop(trip_id, None)
                stop_subscriber = True

        if stop_subscriber:
            task = self._subscriber_tasks.pop(trip_id, None)
            if task is not None:
                task.cancel()

        return is_last_for_user

    async def send_to_user(self, trip_id: str, user_id: str, message: dict) -> None:
        connections = self._connections.get(trip_id, {}).get(user_id, set())
        await self._send_to_many(connections, message)

    async def broadcast_to_trip(self, trip_id: str, message: dict, exclude_user_id: Optional[str] = None) -> None:
        """Local-only send to every connection this process holds for the
        trip. Called by the subscriber loop for every event published on
        the trip's channel, from any instance (including this one)."""
        trip_conns = self._connections.get(trip_id, {})
        targets: Set[WebSocket] = set()
        for uid, conns in trip_conns.items():
            if uid == exclude_user_id:
                continue
            targets |= conns
        await self._send_to_many(targets, message)

    async def close_trip_connections(self, trip_id: str, code: int = 1000) -> None:
        """Used on trip end — closes every local connection for the trip.
        Callers publish the trip_ended frame first so clients see why."""
        trip_conns = self._connections.pop(trip_id, {})
        all_conns = {ws for conns in trip_conns.values() for ws in conns}
        for ws in all_conns:
            try:
                await ws.close(code=code)
            except Exception:
                pass

        task = self._subscriber_tasks.pop(trip_id, None)
        if task is not None:
            task.cancel()

    def connection_count(self, trip_id: str, user_id: str) -> int:
        return len(self._connections.get(trip_id, {}).get(user_id, set()))

    def total_connection_count(self) -> int:
        """Every live connection across every trip — the gauge behind
        GET /metrics' `websocket_active_connections` (see app/api/metrics.py)."""
        return sum(len(conns) for trip_conns in self._connections.values() for conns in trip_conns.values())

    async def close_all(self, code: int = 1001) -> None:
        """Graceful shutdown (Part 12): close every live connection across
        every trip and stop every subscriber task, so the process doesn't
        just vanish out from under connected clients when it exits. 1001
        ("Going Away") — accurate for a server shutdown, distinct from the
        1000 close_trip_connections() uses for an ordinary trip ending."""
        trip_ids = list(self._connections.keys())
        for trip_id in trip_ids:
            await self.close_trip_connections(trip_id, code=code)

    async def _send_to_many(self, connections: Set[WebSocket], message: dict) -> None:
        if not connections:
            return
        payload = json.dumps(message)
        for ws in list(connections):
            try:
                await ws.send_text(payload)
            except Exception:
                # A broken socket here also triggers its own
                # WebSocketDisconnect in its own handler loop, which does
                # the real cleanup — this just stops one bad connection
                # from breaking the broadcast for everyone else.
                logger.debug("Failed to send to a WebSocket; its own handler loop will clean it up.")

    async def _subscribe_loop(self, redis: Redis, trip_id: str) -> None:
        """One long-lived task per trip per process, forwarding
        Redis-published events to this process's local connections.

        A published `trip_ended` event is special: every instance that
        sees it (including the one that published it, since Redis
        delivers to all subscribers of a channel, publisher included)
        closes its own local connections for the trip right after
        forwarding the frame — that's what makes trip-end closing work
        uniformly across instances without each REST endpoint needing to
        know which instances hold which connections.

        Reconnects with bounded exponential backoff (Part 5 — Redis
        resilience) if the Pub/Sub connection itself drops (a Redis
        restart, a network blip) — never a tight retry loop, and never
        infinite: it gives up (and logs it) after REDIS_RETRY_LIMIT
        consecutive failures, and stops retrying altogether the moment
        this trip has no local connections left to serve (checked before
        every retry — no point resurrecting a subscriber for a trip
        nobody here is watching). While disconnected, this instance's
        local clients simply receive no live updates from other
        instances until reconnected — their own location_update sends
        still work, since those go straight to Postgres/Redis directly,
        not through this loop."""
        from app.core.config import settings as _settings
        from app.core import metrics as _metrics

        attempt = 0
        while True:
            if trip_id not in self._connections:
                return  # nobody left to serve — stop retrying.

            pubsub = redis.pubsub()
            try:
                await pubsub.subscribe(trip_channel(trip_id))
                attempt = 0  # a successful (re)connect resets the backoff
                async for raw in pubsub.listen():
                    if raw["type"] != "message":
                        continue
                    try:
                        envelope = json.loads(raw["data"])
                        message = envelope["message"]
                    except (TypeError, ValueError, KeyError):
                        continue

                    await self.broadcast_to_trip(trip_id, message, exclude_user_id=envelope.get("exclude_user_id"))

                    if message.get("type") == "trip_ended":
                        await self.close_trip_connections(trip_id)
                        return  # close_trip_connections already cancels this task, but return cleanly just in case
                return  # pubsub.listen() ended on its own (clean unsubscribe) — nothing more to do.
            except asyncio.CancelledError:
                return
            except Exception:
                attempt += 1
                _metrics.increment("redis_reconnects_total", {"component": "pubsub"})
                if attempt > _settings.REDIS_RETRY_LIMIT:
                    logger.error(
                        "Live-trip subscriber loop for trip %s giving up after %d failed reconnect attempts",
                        trip_id, attempt - 1,
                    )
                    return
                delay = min(2 ** attempt, _settings.REDIS_RETRY_MAX_BACKOFF_SECONDS)
                logger.warning(
                    "Live-trip subscriber loop for trip %s lost its Redis connection (attempt %d/%d) — "
                    "retrying in %.1fs", trip_id, attempt, _settings.REDIS_RETRY_LIMIT, delay,
                )
                try:
                    await asyncio.sleep(delay)
                except asyncio.CancelledError:
                    return
            finally:
                try:
                    await pubsub.unsubscribe(trip_channel(trip_id))
                    await pubsub.aclose()
                except Exception:
                    pass


manager = ConnectionManager()


async def publish_event(redis: Redis, trip_id: str, message: dict, exclude_user_id: Optional[str] = None) -> None:
    """The one place event producers call to fan a message out to every
    instance (including this one, via its own subscriber loop) with a
    live connection for the trip. `exclude_user_id` is transport metadata
    only — it never reaches the client inside `message` itself."""
    envelope = {"message": message, "exclude_user_id": exclude_user_id}
    await redis.publish(trip_channel(trip_id), json.dumps(envelope))
