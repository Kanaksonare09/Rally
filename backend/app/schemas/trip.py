import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import TripStatus


class TripCreate(BaseModel):
    destination_name: Optional[str] = Field(None, max_length=255)
    latitude: Optional[float] = Field(None, ge=-90, le=90)
    longitude: Optional[float] = Field(None, ge=-180, le=180)


class TripStart(BaseModel):
    latitude: Optional[float] = Field(None, ge=-90, le=90)
    longitude: Optional[float] = Field(None, ge=-180, le=180)


class TripResponse(BaseModel):
    id: uuid.UUID
    group_id: uuid.UUID
    status: TripStatus
    started_by: Optional[uuid.UUID] = None
    started_at: Optional[datetime] = None
    ended_at: Optional[datetime] = None
    destination_name: Optional[str] = None
    distance: Optional[float] = None
    duration: Optional[int] = None
    safety_score: Optional[int] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class TripListItem(BaseModel):
    id: uuid.UUID
    status: TripStatus
    started_at: Optional[datetime] = None
    ended_at: Optional[datetime] = None
    destination_name: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)
