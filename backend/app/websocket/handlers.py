"""
Per-connection message handling: parse -> validate -> authorize (cached)
-> persist -> update live state -> publish -> ack. The router
(app/api/websocket.py) stays thin and just calls handle_client_message()
in a loop; all the actual logic lives here.

Persistence strategy for this phase: every valid location_update is
written straight to location_history, synchronously, before the ack is
sent. That's simple and correct, but not the final word — the TODO for a
later pass is swapping the direct `run_in_threadpool(_persist_location)`
call below for a queue/batch writer if GPS volume ever demands it,
without changing this function's external contract (still returns an ack
either way).
"""

import json
import logging
import time
import uuid
from typing import List, Optional

from pydantic import ValidationError
from redis.asyncio import Redis
from sqlalchemy import select
from sqlalchemy.orm import Session
from starlette.concurrency import run_in_threadpool

from app.core.config import settings
from app.core.errors import AppHTTPException
from app.models.enums import MemberStatus
from app.models.group_member import GroupMember
from app.models.profile import Profile
from app.services import live_state_service, location_service, presence_service, trip_service
from app.websocket.auth import TripConnectionContext
from app.websocket.manager import publish_event
from app.websocket.schemas import (
    ClientEnvelope,
    ErrorCode,
    LocationCreate,
    build_error,
    build_heartbeat_ack,
    build_location_ack,
    build_location_update_event,
    build_trip_state,
)

logger = logging.getLogger("rally.websocket")

# AppHTTPException codes raised by location_service.record_location(),
# mapped onto this protocol's own error vocabulary.
_TRIP_SERVICE_ERROR_MAP = {
    "INVALID_TRIP_STATE": ErrorCode.TRIP_NOT_ACTIVE,
    "INVALID_TIMESTAMP": ErrorCode.INVALID_LOCATION,
}


class RateLimiter:
    """Per-connection minimum-interval limiter: rejects a message that
    arrives sooner than `1/max_per_second` after the last *accepted* one.
    Tuned for GPS pacing specifically (MAX_LOCATION_UPDATES_PER_SECOND) —
    a steady drip, not a burst — one instance per WebSocket, no need for
    Redis-backed cross-connection coordination in this phase."""

    def __init__(self, max_per_second: float):
        self._min_interval = 1.0 / max_per_second if max_per_second > 0 else 0.0
        self._last_accepted = 0.0

    def allow(self) -> bool:
        now = time.monotonic()
        if now - self._last_accepted < self._min_interval:
            return False
        self._last_accepted = now
        return True


class WindowRateLimiter:
    """Per-connection fixed one-second-window limiter: allows up to
    `max_per_second` messages within any given second, however they're
    spaced, then rejects until the window rolls over. Used for the
    general WEBSOCKET_MESSAGES_PER_SECOND guard (every message type, not
    just location_update) specifically because it tolerates a legitimate
    quick burst of a few different message types in immediate succession
    — RateLimiter's strict minimum-interval gate would incorrectly flag
    that as flooding; only a genuine high volume within the same second
    trips this one."""

    def __init__(self, max_per_second: int):
        self._max = max_per_second
        self._window_start = 0.0
        self._count = 0

    def allow(self) -> bool:
        now = time.monotonic()
        if now - self._window_start >= 1.0:
            self._window_start = now
            self._count = 0
        self._count += 1
        return self._count <= self._max


class TripActiveFlag:
    """Mutable box holding this connection's cached "is the trip still
    ACTIVE" state. Checked at connect time, then flipped to False either
    by a location_update that discovers INVALID_TRIP_STATE, or by the
    trip_ended broadcast — never re-queried from the DB per message (see
    the module docstring in app/websocket/auth.py for why)."""

    def __init__(self, active: bool = True):
        self.active = active


def _persist_location(db: Session, trip_id: uuid.UUID, user_id: uuid.UUID, data: LocationCreate):
    """Sync DB work — always call through run_in_threadpool. Re-fetches
    the trip (one cheap indexed lookup) so the ACTIVE check is against
    current data, not the connection's possibly-stale cached status."""
    trip = trip_service.get_trip_by_id(db, trip_id)
    if trip is None:
        raise AppHTTPException(status_code=404, code="TRIP_NOT_FOUND", detail="Trip not found.")
    return location_service.record_location(db, trip, user_id, data)


async def handle_client_message(
    *,
    raw: str,
    db: Session,
    redis: Redis,
    ctx: TripConnectionContext,
    rate_limiter: RateLimiter,
    trip_active: TripActiveFlag,
    general_rate_limiter: Optional[WindowRateLimiter] = None,
) -> dict:
    """Returns the frame to send back to the sender. Broadcasting to other
    members (if any) happens as a side effect, via Redis, before this
    returns.

    `general_rate_limiter` (WEBSOCKET_MESSAGES_PER_SECOND) bounds EVERY
    message type — heartbeat, garbage, anything — checked before this
    message is even parsed. `rate_limiter` (MAX_LOCATION_UPDATES_PER_SECOND)
    is the separate, tighter bound specifically on location_update, still
    enforced inside _handle_location_update below; a client can be well
    under the general limit and still get throttled there."""

    if len(raw.encode("utf-8")) > settings.WS_MAX_MESSAGE_BYTES:
        return build_error(ErrorCode.INVALID_MESSAGE, "Message too large.")

    if general_rate_limiter is not None and not general_rate_limiter.allow():
        return build_error(ErrorCode.RATE_LIMITED, "Sending messages too fast — please slow down.")

    try:
        payload = json.loads(raw)
        envelope = ClientEnvelope.model_validate(payload)
    except Exception:
        return build_error(ErrorCode.INVALID_MESSAGE, "Message must be valid JSON with a 'type' field.")

    if envelope.type == "heartbeat":
        await presence_service.mark_online(redis, ctx.trip_id, ctx.user_id)
        return build_heartbeat_ack()

    if envelope.type == "location_update":
        return await _handle_location_update(envelope, db, redis, ctx, rate_limiter, trip_active)

    return build_error(ErrorCode.INVALID_MESSAGE, f"Unknown message type: {envelope.type!r}")


async def _handle_location_update(
    envelope: ClientEnvelope,
    db: Session,
    redis: Redis,
    ctx: TripConnectionContext,
    rate_limiter: RateLimiter,
    trip_active: TripActiveFlag,
) -> dict:
    if not trip_active.active:
        return build_error(ErrorCode.TRIP_NOT_ACTIVE, "This trip has ended; location updates are no longer accepted.")

    if not rate_limiter.allow():
        return build_error(ErrorCode.RATE_LIMITED, "Sending location updates too fast — please slow down.")

    try:
        # Client never supplies user_id/trip_id/group_id — LocationCreate
        # has no such fields, same trust boundary as the REST endpoint.
        data = LocationCreate.model_validate(envelope.data or {})
    except ValidationError:
        return build_error(ErrorCode.INVALID_LOCATION, "Invalid GPS coordinates.")

    try:
        location = await run_in_threadpool(_persist_location, db, ctx.trip_id, ctx.user_id, data)
    except AppHTTPException as exc:
        if exc.code == "INVALID_TRIP_STATE":
            trip_active.active = False
        code = _TRIP_SERVICE_ERROR_MAP.get(exc.code, ErrorCode.INVALID_LOCATION)
        return build_error(code, exc.detail)
    except Exception:
        # A real storage failure (e.g. the DB is unreachable) — the client
        # must never be told this was permanently stored when it wasn't.
        logger.exception("Failed to persist location_update for trip %s", ctx.trip_id)
        return build_location_ack(recorded_at=data.recorded_at.isoformat() if data.recorded_at else "", accepted=False)

    recorded_at_iso = location.recorded_at.isoformat()

    try:
        await live_state_service.set_live_location(
            redis,
            ctx.trip_id,
            ctx.user_id,
            latitude=location.latitude,
            longitude=location.longitude,
            accuracy=location.accuracy,
            speed=location.speed,
            heading=location.heading,
            recorded_at=recorded_at_iso,
            updated_at=recorded_at_iso,
        )
        await presence_service.mark_online(redis, ctx.trip_id, ctx.user_id)

        event = build_location_update_event(
            user_id=ctx.user_id,
            latitude=location.latitude,
            longitude=location.longitude,
            accuracy=location.accuracy,
            speed=location.speed,
            heading=location.heading,
            recorded_at=recorded_at_iso,
        )
        await publish_event(redis, str(ctx.trip_id), event, exclude_user_id=str(ctx.user_id))
    except Exception:
        # The location IS durably stored in Postgres at this point — a
        # live-state/broadcast failure doesn't change that, so this still
        # acks as accepted (Redis is disposable state, not the record of
        # truth) but we log it since other members won't see the update.
        logger.exception("Live state update / broadcast failed for trip %s after successful persistence", ctx.trip_id)

    return build_location_ack(recorded_at=recorded_at_iso, accepted=True)


def _load_active_members(db: Session, group_id: uuid.UUID) -> List[dict]:
    """Sync DB work — always call through run_in_threadpool.

    Active group membership (Postgres) is the authoritative member list;
    Redis only ever supplies *where they currently are* and *whether
    they're online* on top of it — never who's in the group (see the
    "Database vs Redis responsibility" note in the README)."""
    rows = db.execute(
        select(GroupMember, Profile)
        .join(Profile, GroupMember.user_id == Profile.id)
        .where(GroupMember.group_id == group_id, GroupMember.status == MemberStatus.ACTIVE)
    ).all()
    return [
        {"user_id": member.user_id, "name": profile.full_name, "role": member.role.value}
        for member, profile in rows
    ]


async def build_trip_state_snapshot(db: Session, redis: Redis, ctx: TripConnectionContext) -> dict:
    """Sent once, right after a client connects — see the WEBSOCKET
    CONNECTION FLOW step "send current live state" in the router."""
    members = await run_in_threadpool(_load_active_members, db, ctx.group_id)
    user_ids = [m["user_id"] for m in members]

    locations = await live_state_service.get_live_locations(redis, ctx.trip_id, user_ids)
    online_status = await presence_service.get_online_status(redis, ctx.trip_id, user_ids)

    snapshot = []
    for member in members:
        uid_str = str(member["user_id"])
        loc = locations.get(uid_str)
        snapshot.append(
            {
                "user_id": uid_str,
                "name": member["name"],
                "role": member["role"],
                "latitude": loc["latitude"] if loc else None,
                "longitude": loc["longitude"] if loc else None,
                "accuracy": loc["accuracy"] if loc else None,
                "speed": loc["speed"] if loc else None,
                "heading": loc["heading"] if loc else None,
                "recorded_at": loc["recorded_at"] if loc else None,
                "status": "ONLINE" if online_status.get(uid_str) else "OFFLINE",
            }
        )

    return build_trip_state(ctx.trip_id, snapshot)
