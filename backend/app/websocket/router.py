import json
import logging
import uuid
from typing import Optional
from datetime import datetime, timezone
from pydantic import ValidationError

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import select

from app.core.database import session_scope
from app.core.security import decode_supabase_jwt, InvalidTokenError
from app.models.enums import MemberStatus, TripStatus
from app.models.group_member import GroupMember
from app.models.trip import Trip
from app.schemas.location import LocationCreate
from app.services import location_service
from app.redis.client import get_redis
from app.redis.state import (
    set_member_online,
    set_member_offline,
    get_group_live_state,
    set_member_state,
    get_member_state
)
from app.websocket.manager import manager
from app.websocket.schemas import (
    ErrorMessage,
    ErrorMessageData,
    GroupStateMessage,
    GroupStateData,
    IncomingMessage,
    LocationUpdateMessage,
    PingMessage,
    PongMessage,
    SubscribeMessage,
    OutgoingLocationUpdateMessage,
    OutgoingLocationUpdateData,
    MemberStatusMessage,
    MemberStatusData
)

logger = logging.getLogger("rally.websocket")

router = APIRouter()
@router.websocket("/ws/groups/{group_id}")
async def websocket_endpoint(
    websocket: WebSocket,
    group_id: uuid.UUID,
    token: str = Query(...)
):
    # 1. Authentication
    try:
        claims = decode_supabase_jwt(token)
        user_id = uuid.UUID(claims["sub"])
    except InvalidTokenError:
        await websocket.accept()
        await websocket.send_text(ErrorMessage(data=ErrorMessageData(code="UNAUTHORIZED", message="Invalid or expired token.")).model_dump_json())
        await websocket.close(code=1008)
        return
    except ValueError:
        await websocket.accept()
        await websocket.send_text(ErrorMessage(data=ErrorMessageData(code="INVALID_MESSAGE", message="Invalid user ID format in token.")).model_dump_json())
        await websocket.close(code=1008)
        return

    # 2. Authorization (Group Membership)
    with session_scope() as db:
        member = db.scalars(
            select(GroupMember).where(
                GroupMember.group_id == group_id, GroupMember.user_id == user_id
            )
        ).first()

        if not member or member.status != MemberStatus.ACTIVE:
            await websocket.accept()
            await websocket.send_text(ErrorMessage(data=ErrorMessageData(code="FORBIDDEN", message="Not an active member of this group.")).model_dump_json())
            await websocket.close(code=1008)
            return

    # 3. Connection accepted
    await manager.connect(group_id, user_id, websocket)
    redis_client_generator = get_redis()
    redis_client = await anext(redis_client_generator)

    try:
        # Mark online
        await set_member_online(redis_client, group_id, user_id)

        # Broadcast online status
        await manager.broadcast_to_group(
            group_id,
            MemberStatusMessage(data=MemberStatusData(user_id=user_id, status="ONLINE")),
            exclude_user_id=user_id
        )

        # Send current group state
        with session_scope() as db:
            active_trip = db.scalars(
                select(Trip).where(Trip.group_id == group_id, Trip.status == TripStatus.ACTIVE)
            ).first()
            trip_id = active_trip.id if active_trip else uuid.UUID(int=0)
            
        group_state = await get_group_live_state(redis_client, group_id)
        await manager.send_to_user(
            group_id, user_id,
            GroupStateMessage(data=GroupStateData(group_id=group_id, trip_id=trip_id, members=group_state))
        )

        # 4. Message loop
        while True:
            text_data = await websocket.receive_text()
            try:
                json_data = json.loads(text_data)
                
                # Manual discriminator since pydantic union discrimination can be tricky with types
                msg_type = json_data.get("type")
                if msg_type == "ping":
                    msg = PingMessage(**json_data)
                    await manager.send_to_user(group_id, user_id, PongMessage(data={"timestamp": datetime.now(timezone.utc).isoformat()}))
                    continue
                elif msg_type == "subscribe":
                    continue # already subscribed conceptually
                elif msg_type == "location_update":
                    msg = LocationUpdateMessage(**json_data)
                else:
                    await manager.send_to_user(group_id, user_id, ErrorMessage(data=ErrorMessageData(code="INVALID_MESSAGE", message="Unknown message type.")))
                    continue
            except (json.JSONDecodeError, ValidationError) as e:
                await manager.send_to_user(group_id, user_id, ErrorMessage(data=ErrorMessageData(code="INVALID_MESSAGE", message="Invalid message format.")))
                continue

            if msg.type == "location_update":
                # Validate active trip
                with session_scope() as db:
                    active_trip = db.scalars(
                        select(Trip).where(Trip.group_id == group_id, Trip.status == TripStatus.ACTIVE)
                    ).first()

                    if not active_trip:
                        await manager.send_to_user(group_id, user_id, ErrorMessage(data=ErrorMessageData(code="NO_ACTIVE_TRIP", message="No active trip for this group.")))
                        continue

                    # Persist location history
                    try:
                        loc_create = LocationCreate(
                            latitude=msg.data.latitude,
                            longitude=msg.data.longitude,
                            accuracy=msg.data.accuracy,
                            speed=msg.data.speed,
                            heading=msg.data.heading,
                            recorded_at=msg.data.recorded_at
                        )
                        location_service.record_location(db, active_trip, user_id, loc_create)
                    except Exception as e:
                        logger.error(f"Error persisting location: {e}")
                        # Don't crash, just proceed to update live state if possible

                # Update live state in Redis
                state = await get_member_state(redis_client, group_id, user_id) or {}
                state.update({
                    "user_id": str(user_id),
                    "trip_id": str(active_trip.id),
                    "latitude": msg.data.latitude,
                    "longitude": msg.data.longitude,
                    "accuracy": msg.data.accuracy,
                    "speed": msg.data.speed,
                    "heading": msg.data.heading,
                    "recorded_at": msg.data.recorded_at.isoformat() if msg.data.recorded_at else datetime.now(timezone.utc).isoformat(),
                    "connection_state": "ONLINE",
                    "last_seen": datetime.now(timezone.utc).isoformat()
                })
                await set_member_state(redis_client, group_id, user_id, state)

                # Broadcast to group
                out_msg = OutgoingLocationUpdateMessage(
                    data=OutgoingLocationUpdateData(
                        user_id=user_id,
                        last_seen=datetime.fromisoformat(state["last_seen"]),
                        **msg.data.model_dump()
                    )
                )
                await manager.broadcast_to_group(group_id, out_msg, exclude_user_id=user_id)

    except WebSocketDisconnect:
        is_last = manager.disconnect(group_id, user_id, websocket)
        if is_last:
            await set_member_offline(redis_client, group_id, user_id)
            await manager.broadcast_to_group(
                group_id,
                MemberStatusMessage(data=MemberStatusData(user_id=user_id, status="OFFLINE"))
            )
