import uuid
from datetime import datetime
from typing import Any, Dict, Optional

from pydantic import BaseModel, Field

from app.models.enums import SOSStatus

DEFAULT_SOS_LIMIT = 100
MAX_SOS_LIMIT = 1000


class SOSCreate(BaseModel):
    latitude: float = Field(..., ge=-90, le=90)
    longitude: float = Field(..., ge=-180, le=180)
    accuracy: Optional[float] = Field(None, ge=0)
    message: Optional[str] = Field(None, max_length=1000)


class SOSResponse(BaseModel):
    id: uuid.UUID
    trip_id: uuid.UUID
    user_id: Optional[uuid.UUID] = None
    latitude: float
    longitude: float
    accuracy: Optional[float] = None
    message: Optional[str] = None
    status: SOSStatus
    metadata: Dict[str, Any] = Field(default_factory=dict)
    triggered_at: datetime
    acknowledged_at: Optional[datetime] = None
    resolved_at: Optional[datetime] = None
    created_at: datetime
