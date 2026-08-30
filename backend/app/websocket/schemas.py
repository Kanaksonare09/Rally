"""
The WebSocket wire protocol, in one place. Every message — either
direction — is `{"type": "...", "data": {...}}`. `type` is what makes this
versionable: a client that doesn't recognize a given type can ignore it
instead of breaking.

Client -> server: "location_update", "heartbeat" (see ClientMessageType).
Server -> client: "trip_state", "location_update", "location_ack",
"presence_update", "trip_ended", "heartbeat_ack", "error"
(see ServerMessageType). Full protocol documented in the backend README.
"""

import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict

# Re-exported so the rest of the websocket package validates incoming GPS
# fields with the exact same rules as the REST endpoint — one source of
# truth for "what is a valid location."
from app.schemas.location import LocationCreate  # noqa: F401


class ClientMessageType(str, Enum):
    LOCATION_UPDATE = "location_update"
    HEARTBEAT = "heartbeat"


class ServerMessageType(str, Enum):
    TRIP_STATE = "trip_state"
    LOCATION_UPDATE = "location_update"
    LOCATION_ACK = "location_ack"
    PRESENCE_UPDATE = "presence_update"
    TRIP_ENDED = "trip_ended"
    HEARTBEAT_ACK = "heartbeat_ack"
    INTELLIGENCE_EVENT = "intelligence_event"
    ALERT = "alert"
    ALERT_UPDATED = "alert_updated"
    SOS = "sos"
    SOS_UPDATED = "sos_updated"
    ROUTE_PROGRESS = "route_progress"
    ROUTE_DEVIATION = "route_deviation"
    ERROR = "error"


class PresenceStatus(str, Enum):
    ONLINE = "ONLINE"
    OFFLINE = "OFFLINE"


class ErrorCode(str, Enum):
    UNAUTHORIZED = "UNAUTHORIZED"
    TRIP_NOT_FOUND = "TRIP_NOT_FOUND"
    TRIP_NOT_ACTIVE = "TRIP_NOT_ACTIVE"
    NOT_A_MEMBER = "NOT_A_MEMBER"
    INVALID_MESSAGE = "INVALID_MESSAGE"
    INVALID_LOCATION = "INVALID_LOCATION"
    RATE_LIMITED = "RATE_LIMITED"
    INTERNAL_ERROR = "INTERNAL_ERROR"


class ClientEnvelope(BaseModel):
    """Outer shape of every client -> server message. `data`'s inner shape
    depends on `type` and is validated separately per message type (e.g.
    against LocationCreate for location_update) — see handlers.py."""

    model_config = ConfigDict(extra="ignore")

    type: str
    data: Optional[Dict[str, Any]] = None


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def build_error(code, message: str) -> dict:
    """`code` may be an ErrorCode or a plain string (WebSocketAuthError and
    AppHTTPException both carry codes as plain strings) — normalized here
    so callers never have to think about which."""
    code_value = code.value if isinstance(code, ErrorCode) else str(code)
    return {"type": ServerMessageType.ERROR.value, "data": {"code": code_value, "message": message}}


def build_location_ack(recorded_at: str, accepted: bool = True) -> dict:
    return {
        "type": ServerMessageType.LOCATION_ACK.value,
        "data": {"recorded_at": recorded_at, "accepted": accepted},
    }


def build_heartbeat_ack() -> dict:
    return {"type": ServerMessageType.HEARTBEAT_ACK.value, "data": {"server_time": _now_iso()}}


def build_location_update_event(
    user_id: uuid.UUID,
    latitude: float,
    longitude: float,
    accuracy: Optional[float],
    speed: Optional[float],
    heading: Optional[float],
    recorded_at: str,
) -> dict:
    """The server-constructed broadcast event — never the client's raw
    message. The server decides exactly what fields other members see."""
    return {
        "type": ServerMessageType.LOCATION_UPDATE.value,
        "data": {
            "user_id": str(user_id),
            "latitude": latitude,
            "longitude": longitude,
            "accuracy": accuracy,
            "speed": speed,
            "heading": heading,
            "recorded_at": recorded_at,
            "updated_at": _now_iso(),
        },
    }


def build_presence_update(user_id: uuid.UUID, status: PresenceStatus) -> dict:
    return {
        "type": ServerMessageType.PRESENCE_UPDATE.value,
        "data": {"user_id": str(user_id), "status": status.value},
    }


def build_trip_state(trip_id: uuid.UUID, members: List[Dict[str, Any]]) -> dict:
    return {"type": ServerMessageType.TRIP_STATE.value, "data": {"trip_id": str(trip_id), "members": members}}


def build_trip_ended(trip_id: uuid.UUID, status: str) -> dict:
    return {"type": ServerMessageType.TRIP_ENDED.value, "data": {"trip_id": str(trip_id), "status": status}}


def build_intelligence_event(
    event_type: str,
    severity: str,
    user_id: Optional[uuid.UUID],
    related_user_id: Optional[uuid.UUID],
    detected_at: str,
    resolved_at: Optional[str],
    metadata: Dict[str, Any],
) -> dict:
    """Published by app/intelligence/engine.py — the intelligence engine
    itself has no idea WebSockets exist (see that module's docstring);
    this is the one shared vocabulary point between the two."""
    return {
        "type": ServerMessageType.INTELLIGENCE_EVENT.value,
        "data": {
            "event_type": event_type,
            "severity": severity,
            "user_id": str(user_id) if user_id else None,
            "related_user_id": str(related_user_id) if related_user_id else None,
            "detected_at": detected_at,
            "resolved_at": resolved_at,
            "metadata": metadata,
        },
    }


def build_alert(
    alert_id: uuid.UUID,
    alert_type: str,
    severity: str,
    title: str,
    message: str,
    user_id: Optional[uuid.UUID],
    created_at: str,
) -> dict:
    """Published by app/alerts/service.py when the Alert Engine decides an
    intelligence event should become a user-facing alert."""
    return {
        "type": ServerMessageType.ALERT.value,
        "data": {
            "id": str(alert_id),
            "alert_type": alert_type,
            "severity": severity,
            "title": title,
            "message": message,
            "user_id": str(user_id) if user_id else None,
            "created_at": created_at,
        },
    }


def build_alert_updated(alert_id: uuid.UUID, status: str) -> dict:
    return {"type": ServerMessageType.ALERT_UPDATED.value, "data": {"alert_id": str(alert_id), "status": status}}


def build_sos(
    sos_id: uuid.UUID,
    trip_id: uuid.UUID,
    user_id: uuid.UUID,
    latitude: float,
    longitude: float,
    accuracy: Optional[float],
    message: Optional[str],
    status: str,
    triggered_at: str,
) -> dict:
    """Published by app/sos/service.py the instant an SOS is triggered —
    delivered immediately, never batched with routine location updates."""
    return {
        "type": ServerMessageType.SOS.value,
        "data": {
            "id": str(sos_id),
            "trip_id": str(trip_id),
            "user_id": str(user_id),
            "latitude": latitude,
            "longitude": longitude,
            "accuracy": accuracy,
            "message": message,
            "status": status,
            "triggered_at": triggered_at,
        },
    }


def build_sos_updated(sos_id: uuid.UUID, status: str) -> dict:
    return {"type": ServerMessageType.SOS_UPDATED.value, "data": {"sos_id": str(sos_id), "status": status}}


def build_route_progress(
    trip_id: uuid.UUID,
    route_id: uuid.UUID,
    group_route_fraction: Optional[float],
    trip_arrived: bool,
    members: List[Dict[str, Any]],
) -> dict:
    """Published by app/intelligence/engine.py's route evaluation on every
    tick a trip has an ACTIVE route — a continuous live readout, not a
    discrete event, so (unlike intelligence_event/alert) it's sent every
    tick regardless of whether anything changed since the last one."""
    return {
        "type": ServerMessageType.ROUTE_PROGRESS.value,
        "data": {
            "trip_id": str(trip_id),
            "route_id": str(route_id),
            "group_route_fraction": group_route_fraction,
            "trip_arrived": trip_arrived,
            "members": members,
            "server_time": _now_iso(),
        },
    }


def build_route_deviation(
    user_id: Optional[uuid.UUID],
    distance_from_route_meters: Optional[float],
    status: str,
    detected_at: str,
) -> dict:
    """Published in addition to (not instead of) the generic
    intelligence_event frame that already carries every ROUTE_DEVIATION
    created/resolved transition — this is a route-specific convenience
    frame for clients that only care about route deviations, not every
    intelligence event type. `status` is "DEVIATED" or "BACK_ON_ROUTE"."""
    return {
        "type": ServerMessageType.ROUTE_DEVIATION.value,
        "data": {
            "user_id": str(user_id) if user_id else None,
            "distance_from_route_meters": distance_from_route_meters,
            "status": status,
            "detected_at": detected_at,
        },
    }
