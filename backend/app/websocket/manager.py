import uuid
from typing import Dict, List
from fastapi import WebSocket
from pydantic import BaseModel

class ConnectionManager:
    def __init__(self):
        # group_id -> user_id -> List[WebSocket]
        self.active_connections: Dict[str, Dict[str, List[WebSocket]]] = {}

    async def connect(self, group_id: uuid.UUID, user_id: uuid.UUID, websocket: WebSocket):
        await websocket.accept()
        g_id = str(group_id)
        u_id = str(user_id)
        
        if g_id not in self.active_connections:
            self.active_connections[g_id] = {}
        if u_id not in self.active_connections[g_id]:
            self.active_connections[g_id][u_id] = []
            
        self.active_connections[g_id][u_id].append(websocket)

    def disconnect(self, group_id: uuid.UUID, user_id: uuid.UUID, websocket: WebSocket) -> bool:
        """
        Removes the connection. Returns True if this was the LAST connection for this user.
        """
        g_id = str(group_id)
        u_id = str(user_id)
        
        is_last_connection = False
        if g_id in self.active_connections and u_id in self.active_connections[g_id]:
            if websocket in self.active_connections[g_id][u_id]:
                self.active_connections[g_id][u_id].remove(websocket)
            
            if len(self.active_connections[g_id][u_id]) == 0:
                is_last_connection = True
                del self.active_connections[g_id][u_id]
                
            if len(self.active_connections[g_id]) == 0:
                del self.active_connections[g_id]
                
        return is_last_connection

    async def broadcast_to_group(self, group_id: uuid.UUID, message: BaseModel, exclude_user_id: uuid.UUID | None = None):
        g_id = str(group_id)
        if g_id not in self.active_connections:
            return
            
        msg_json = message.model_dump_json()
        for u_id, sockets in self.active_connections[g_id].items():
            if exclude_user_id and u_id == str(exclude_user_id):
                continue
            for ws in sockets:
                try:
                    await ws.send_text(msg_json)
                except Exception:
                    pass

    async def send_to_user(self, group_id: uuid.UUID, user_id: uuid.UUID, message: BaseModel):
        g_id = str(group_id)
        u_id = str(user_id)
        if g_id in self.active_connections and u_id in self.active_connections[g_id]:
            msg_json = message.model_dump_json()
            for ws in self.active_connections[g_id][u_id]:
                try:
                    await ws.send_text(msg_json)
                except Exception:
                    pass

manager = ConnectionManager()
