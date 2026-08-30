import uuid
from datetime import datetime
from typing import Any, Dict, List, Literal, Optional, Union
from pydantic import BaseModel, Field

# -----------------
# INCOMING MESSAGES
# -----------------

class BaseIncomingMessage(BaseModel):
    type: str

class LocationUpdateData(BaseModel):
    latitude: float = Field(..., ge=-90, le=90)
    longitude: float = Field(..., ge=-180, le=180)
    accuracy: Optional[float] = Field(None, ge=0)
    speed: Optional[float] = Field(None, ge=0)
    heading: Optional[float] = Field(None, ge=0, lt=360)
    recorded_at: Optional[datetime] = None

class LocationUpdateMessage(BaseIncomingMessage):
    type: Literal["location_update"]
    data: LocationUpdateData

class PingMessage(BaseIncomingMessage):
    type: Literal["ping"]

class SubscribeMessage(BaseIncomingMessage):
    type: Literal["subscribe"]

IncomingMessage = Union[LocationUpdateMessage, PingMessage, SubscribeMessage]


# -----------------
# OUTGOING MESSAGES
# -----------------

class BaseOutgoingMessage(BaseModel):
    type: str

class OutgoingLocationUpdateData(LocationUpdateData):
    user_id: uuid.UUID
    last_seen: datetime

class OutgoingLocationUpdateMessage(BaseOutgoingMessage):
    type: Literal["location_update"] = "location_update"
    data: OutgoingLocationUpdateData

class MemberStatusData(BaseModel):
    user_id: uuid.UUID
    status: Literal["ONLINE", "OFFLINE"]

class MemberStatusMessage(BaseOutgoingMessage):
    type: Literal["member_status"] = "member_status"
    data: MemberStatusData

class GroupStateData(BaseModel):
    group_id: uuid.UUID
    trip_id: uuid.UUID
    members: List[Dict[str, Any]]

class GroupStateMessage(BaseOutgoingMessage):
    type: Literal["group_state"] = "group_state"
    data: GroupStateData

class PongMessage(BaseOutgoingMessage):
    type: Literal["pong"] = "pong"
    data: Dict[str, str]

class ErrorMessageData(BaseModel):
    code: str
    message: str

class ErrorMessage(BaseOutgoingMessage):
    type: Literal["error"] = "error"
    data: ErrorMessageData
