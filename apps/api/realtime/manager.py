from typing import Dict, List, Set
from fastapi import WebSocket
import json
import logging

logger = logging.getLogger(__name__)

class ConnectionManager:
    def __init__(self):
        # trip_id -> Set of WebSockets
        self.active_connections: Dict[str, Set[WebSocket]] = {}
        # websocket -> (user_id, trip_id)
        self.connection_meta: Dict[WebSocket, Dict[str, str]] = {}

    async def connect(self, websocket: WebSocket, trip_id: str, user_id: str):
        await websocket.accept()
        if trip_id not in self.active_connections:
            self.active_connections[trip_id] = set()
        self.active_connections[trip_id].add(websocket)
        self.connection_meta[websocket] = {"trip_id": trip_id, "user_id": user_id}
        logger.info(f"WebSocket connected: User {user_id} joined Trip {trip_id}")

    def disconnect(self, websocket: WebSocket):
        meta = self.connection_meta.get(websocket)
        if meta:
            trip_id = meta["trip_id"]
            user_id = meta["user_id"]
            if trip_id in self.active_connections:
                self.active_connections[trip_id].discard(websocket)
                if not self.active_connections[trip_id]:
                    del self.active_connections[trip_id]
            del self.connection_meta[websocket]
            logger.info(f"WebSocket disconnected: User {user_id} left Trip {trip_id}")

    async def broadcast_to_trip(self, trip_id: str, event_data: dict):
        if trip_id in self.active_connections:
            message = json.dumps(event_data)
            dead_sockets = []
            for connection in self.active_connections[trip_id]:
                try:
                    await connection.send_text(message)
                except Exception as e:
                    logger.error(f"Error sending WS message: {e}")
                    dead_sockets.append(connection)

            for dead in dead_sockets:
                self.disconnect(dead)

manager = ConnectionManager()
