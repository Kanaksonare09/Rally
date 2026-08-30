"""
WS /api/v1/ws/trips/{trip_id} — the live tracking WebSocket.

Kept thin on purpose: this module only accepts the connection,
authenticates/authorizes it, wires up the connection manager, and runs
the receive loop, delegating every actual decision to
app/websocket/{auth,handlers,manager}.py.

Authentication note: browsers' native WebSocket API cannot set custom
request headers, so the token travels as a query parameter —
`/ws/trips/{trip_id}?token=<supabase_access_token>`. That's weaker than an
Authorization header (the token can end up in server access logs or
browser history) but is the standard pattern for browser WebSocket auth
without a bespoke sub-protocol handshake. Mitigations: this endpoint is
wss:// only in production (TLS), the token is short-lived (Supabase
access tokens expire), and it is never logged here (see the deliberate
absence of the raw query string from any log call in this module).

Accept-then-reject: this handshake accepts the WebSocket *before* running
authorization, then immediately sends a structured `error` frame and
closes with an application-specific 4xxx code if authorization fails.
Rejecting before accept is arguably "more correct" HTTP-handshake-wise,
but leaves the browser client with only a bare numeric close code and
almost no diagnostic value — accepting first lets the client actually see
*why* (UNAUTHORIZED vs TRIP_NOT_ACTIVE vs NOT_A_MEMBER), which matters
for building a decent UI around this.
"""

import logging
import uuid

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.core import metrics
from app.core.config import settings
from app.core.database import SessionLocal
from app.core.redis import get_redis
from app.services import presence_service
from app.websocket.auth import WebSocketAuthError, authenticate_token, authorize_connection
from app.websocket.handlers import (
    RateLimiter,
    TripActiveFlag,
    WindowRateLimiter,
    build_trip_state_snapshot,
    handle_client_message,
)
from app.websocket.manager import manager, publish_event
from app.websocket.schemas import PresenceStatus, build_error, build_presence_update, build_trip_ended

logger = logging.getLogger("rally.websocket")

router = APIRouter(tags=["WebSocket"])

# Close codes in the 4000-4999 range are reserved for application use
# (RFC 6455) — 1xxx codes are the protocol's own and shouldn't be reused
# for app-level reasons.
_CLOSE_UNAUTHORIZED = 4401
_CLOSE_NOT_FOUND = 4404
_CLOSE_FORBIDDEN = 4403
_CLOSE_SERVER_ERROR = 4500

_CLOSE_TOO_MANY_CONNECTIONS = 4429  # not an RFC 6455 standard code; app-defined, in the reserved 4000-4999 range
_CLOSE_FLOODING = 4408

_AUTH_ERROR_CLOSE_CODES = {
    "UNAUTHORIZED": _CLOSE_UNAUTHORIZED,
    "TRIP_NOT_FOUND": _CLOSE_NOT_FOUND,
    "NOT_A_MEMBER": _CLOSE_FORBIDDEN,
    "TRIP_NOT_ACTIVE": _CLOSE_FORBIDDEN,
}


@router.websocket("/ws/trips/{trip_id}")
async def trip_websocket(websocket: WebSocket, trip_id: uuid.UUID) -> None:
    await websocket.accept()

    try:
        redis = get_redis()
    except RuntimeError:
        await websocket.send_json(build_error("INTERNAL_ERROR", "Live tracking is temporarily unavailable."))
        await websocket.close(code=_CLOSE_SERVER_ERROR)
        return

    token = websocket.query_params.get("token")
    try:
        user_id_str = authenticate_token(token)
    except WebSocketAuthError as exc:
        await websocket.send_json(build_error(exc.code, exc.message))
        await websocket.close(code=_AUTH_ERROR_CLOSE_CODES.get(exc.code, _CLOSE_UNAUTHORIZED))
        return

    if SessionLocal is None:
        await websocket.send_json(build_error("INTERNAL_ERROR", "Service is temporarily unavailable."))
        await websocket.close(code=_CLOSE_SERVER_ERROR)
        return

    db = SessionLocal()
    try:
        user_id = uuid.UUID(user_id_str)
        try:
            ctx = await authorize_connection(db, trip_id, user_id)
        except WebSocketAuthError as exc:
            await websocket.send_json(build_error(exc.code, exc.message))
            await websocket.close(code=_AUTH_ERROR_CLOSE_CODES.get(exc.code, _CLOSE_FORBIDDEN))
            return

        trip_id_str = str(ctx.trip_id)
        user_id_str = str(ctx.user_id)

        # Connection-limit-per-user (Part 4): reject the new connection
        # rather than closing an existing one — for a live-tracking safety
        # app, silently dropping some *other*, possibly still-in-use tab/
        # device is the more surprising and riskier policy of the two.
        if manager.connection_count(trip_id_str, user_id_str) >= settings.MAX_WS_CONNECTIONS_PER_USER:
            await websocket.send_json(
                build_error("RATE_LIMITED", "Too many live-tracking connections for this trip already open.")
            )
            await websocket.close(code=_CLOSE_TOO_MANY_CONNECTIONS)
            return

        is_first_connection = await manager.connect(redis, trip_id_str, user_id_str, websocket)
        metrics.set_gauge("websocket_active_connections", manager.total_connection_count())
        metrics.increment("websocket_connections_total")
        logger.info("WebSocket connected: trip_id=%s user_id=%s", trip_id_str, user_id_str)

        try:
            await presence_service.mark_online(redis, ctx.trip_id, ctx.user_id)
            if is_first_connection:
                await publish_event(
                    redis, trip_id_str, build_presence_update(ctx.user_id, PresenceStatus.ONLINE)
                )

            snapshot = await build_trip_state_snapshot(db, redis, ctx)
            await websocket.send_json(snapshot)

            rate_limiter = RateLimiter(max_per_second=settings.MAX_LOCATION_UPDATES_PER_SECOND)
            general_rate_limiter = WindowRateLimiter(max_per_second=int(settings.WEBSOCKET_MESSAGES_PER_SECOND))
            trip_active = TripActiveFlag(active=True)
            consecutive_rate_limited = 0

            while True:
                raw = await websocket.receive_text()
                response = await handle_client_message(
                    raw=raw, db=db, redis=redis, ctx=ctx, rate_limiter=rate_limiter, trip_active=trip_active,
                    general_rate_limiter=general_rate_limiter,
                )
                await websocket.send_json(response)

                if response.get("type") == "error" and response.get("data", {}).get("code") == "RATE_LIMITED":
                    consecutive_rate_limited += 1
                    if consecutive_rate_limited >= settings.WEBSOCKET_FLOOD_DISCONNECT_THRESHOLD:
                        logger.warning(
                            "Disconnecting trip %s WebSocket for user %s: %d consecutive rate-limited messages",
                            trip_id_str, user_id_str, consecutive_rate_limited,
                        )
                        await websocket.close(code=_CLOSE_FLOODING)
                        return
                else:
                    consecutive_rate_limited = 0

        except WebSocketDisconnect:
            pass
        except Exception:
            logger.exception("Unhandled error on trip %s WebSocket for user %s", trip_id_str, user_id_str)
        finally:
            is_last_connection = await manager.disconnect(trip_id_str, user_id_str, websocket)
            metrics.set_gauge("websocket_active_connections", manager.total_connection_count())
            metrics.increment("websocket_disconnects_total")
            logger.info("WebSocket disconnected: trip_id=%s user_id=%s", trip_id_str, user_id_str)
            if is_last_connection:
                await presence_service.clear_presence(redis, ctx.trip_id, ctx.user_id)
                try:
                    await publish_event(
                        redis, trip_id_str, build_presence_update(ctx.user_id, PresenceStatus.OFFLINE)
                    )
                except Exception:
                    logger.exception("Failed to publish OFFLINE presence for trip %s", trip_id_str)
    finally:
        db.close()
