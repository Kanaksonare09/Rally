import uuid
from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field

DEFAULT_LOCATION_HISTORY_LIMIT = 500
MAX_LOCATION_HISTORY_LIMIT = 5000


class LocationCreate(BaseModel):
    latitude: float = Field(..., ge=-90, le=90)
    longitude: float = Field(..., ge=-180, le=180)
    accuracy: Optional[float] = Field(None, ge=0)
    # Device-reported speed, assumed meters/second — never derived from
    # coordinates in this phase.
    speed: Optional[float] = Field(None, ge=0)
    # Degrees: 0 = North, 90 = East, 180 = South, 270 = West.
    heading: Optional[float] = Field(None, ge=0, lt=360)
    recorded_at: Optional[datetime] = None


class LocationResponse(BaseModel):
    id: uuid.UUID
    trip_id: uuid.UUID
    user_id: uuid.UUID
    latitude: float
    longitude: float
    accuracy: Optional[float] = None
    speed: Optional[float] = None
    heading: Optional[float] = None
    recorded_at: datetime
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class LocationHistoryItem(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    latitude: float
    longitude: float
    accuracy: Optional[float] = None
    speed: Optional[float] = None
    heading: Optional[float] = None
    recorded_at: datetime

    model_config = ConfigDict(from_attributes=True)


class LocationHistoryQuery(BaseModel):
    """Internal shape the router assembles from validated query params and
    hands to the service — keeps the filter/limit/cursor contract typed in
    one place rather than passing five loose arguments around."""

    from_time: Optional[datetime] = None
    to_time: Optional[datetime] = None
    user_id: Optional[uuid.UUID] = None
    limit: int = Field(DEFAULT_LOCATION_HISTORY_LIMIT, ge=1, le=MAX_LOCATION_HISTORY_LIMIT)
    # Keyset pagination: pass the recorded_at of the last point you already
    # have to get only points strictly after it, still ordered ascending.
    cursor: Optional[datetime] = None


LocationHistoryResponse = List[LocationHistoryItem]
