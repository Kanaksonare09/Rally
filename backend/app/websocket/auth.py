"""
WebSocket authentication + authorization — the WS equivalent of
app/dependencies/{auth,trip}.py. Kept separate because a WebSocket route
can't lean on FastAPI's HTTPException-raising Depends() chain the way HTTP
routes do (there's no "401 response" for a connection that was never
accepted) — every failure here is instead reported via WebSocketAuthError,
which the route turns into an error frame + a close.
"""

import uuid
from dataclasses import dataclass
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session
from starlette.concurrency import run_in_threadpool

from app.core.security import InvalidTokenError, decode_supabase_jwt
from app.models.enums import MemberRole, MemberStatus, TripStatus
from app.models.group_member import GroupMember
from app.services import trip_service


class WebSocketAuthError(Exception):
    """`code` matches app.websocket.schemas.ErrorCode."""

    def __init__(self, code: str, message: str):
        self.code = code
        self.message = message
        super().__init__(message)


@dataclass
class TripConnectionContext:
    """Everything the connection needs, resolved once at connect time and
    cached for the life of the socket — see handlers.py for why this isn't
    re-queried on every message."""

    user_id: uuid.UUID
    trip_id: uuid.UUID
    group_id: uuid.UUID
    role: MemberRole


def authenticate_token(token: Optional[str]) -> str:
    """Verifies the JWT and returns the user id (the `sub` claim). Pure
    CPU work, no I/O — safe to call directly from async code."""
    if not token:
        raise WebSocketAuthError("UNAUTHORIZED", "Authentication required.")
    try:
        claims = decode_supabase_jwt(token)
    except InvalidTokenError as exc:
        raise WebSocketAuthError("UNAUTHORIZED", str(exc)) from exc
    return claims["sub"]


def _load_trip_and_membership(db: Session, trip_id: uuid.UUID, user_id: uuid.UUID) -> TripConnectionContext:
    """Sync DB work — always call through run_in_threadpool from async
    code, never directly.

    Order matters here: membership is checked before trip status, so an
    unauthorized caller learns nothing about a trip's status before we've
    confirmed they're allowed to know it exists at all (security section
    item 1 — "user cannot connect to another group's trip")."""
    trip = trip_service.get_trip_by_id(db, trip_id)
    if not trip:
        raise WebSocketAuthError("TRIP_NOT_FOUND", "Trip not found.")

    member = db.scalars(
        select(GroupMember).where(GroupMember.group_id == trip.group_id, GroupMember.user_id == user_id)
    ).first()
    if not member or member.status != MemberStatus.ACTIVE:
        raise WebSocketAuthError("NOT_A_MEMBER", "You are not an active member of this trip's group.")

    if trip.status != TripStatus.ACTIVE:
        raise WebSocketAuthError("TRIP_NOT_ACTIVE", "This trip is not currently active.")

    return TripConnectionContext(user_id=user_id, trip_id=trip.id, group_id=trip.group_id, role=member.role)


async def authorize_connection(db: Session, trip_id: uuid.UUID, user_id: uuid.UUID) -> TripConnectionContext:
    """Full connect-time check: trip exists, caller is an ACTIVE member of
    its group, and the trip is currently ACTIVE. Wrapped in a threadpool
    so the sync DB session never blocks the event loop."""
    return await run_in_threadpool(_load_trip_and_membership, db, trip_id, user_id)
