from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query
from apps.api.realtime.manager import manager
from apps.api.core.security import decode_token
import json
import logging

logger = logging.getLogger(__name__)

router = APIRouter()

@router.websocket("/ws")
async def websocket_endpoint(
    websocket: WebSocket,
    token: str = Query(...),
    trip_id: str = Query(...)
):
    # Decode token & authorize user
    payload = decode_token(token)
    if not payload or "sub" not in payload:
        await websocket.close(code=4001, reason="Unauthorized JWT token")
        return

    user_id = payload["sub"]
    await manager.connect(websocket, trip_id, user_id)

    try:
        while True:
            data = await websocket.receive_text()
            try:
                event_data = json.loads(data)
                # Broadcast payload to all members in trip room
                await manager.broadcast_to_trip(trip_id, event_data)
            except json.JSONDecodeError:
                logger.warning("Received invalid non-JSON WebSocket frame")
    except WebSocketDisconnect:
        manager.disconnect(websocket)
