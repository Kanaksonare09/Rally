import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from app.models.enums import IntelligenceEventType, IntelligenceSeverity

DEFAULT_INTELLIGENCE_EVENTS_LIMIT = 100
MAX_INTELLIGENCE_EVENTS_LIMIT = 1000


class MemberIntelligenceState(BaseModel):
    user_id: str
    name: Optional[str] = None
    role: str
    movement_state: str  # "MOVING" | "STOPPED" | "STALE" | "OFFLINE"
    presence: str  # "ONLINE" | "OFFLINE"
    location_age_seconds: Optional[float] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    speed: Optional[float] = None
    distance_from_group_center_meters: Optional[float] = None
    is_isolated: bool
    is_falling_behind: bool


class IntelligenceEventResponse(BaseModel):
    id: uuid.UUID
    trip_id: uuid.UUID
    event_type: IntelligenceEventType
    severity: IntelligenceSeverity
    user_id: Optional[uuid.UUID] = None
    related_user_id: Optional[uuid.UUID] = None
    detected_at: datetime
    resolved_at: Optional[datetime] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class TripIntelligenceResponse(BaseModel):
    trip_id: uuid.UUID
    group_state: str
    members: List[MemberIntelligenceState]
    active_events: List[IntelligenceEventResponse]


class IntelligenceEventQuery(BaseModel):
    """Assembled by the router from validated query params — same
    pattern as app/schemas/location.py's LocationHistoryQuery."""

    event_type: Optional[IntelligenceEventType] = None
    severity: Optional[IntelligenceSeverity] = None
    user_id: Optional[uuid.UUID] = None
    active_only: bool = False
    from_time: Optional[datetime] = None
    to_time: Optional[datetime] = None
    limit: int = Field(DEFAULT_INTELLIGENCE_EVENTS_LIMIT, ge=1, le=MAX_INTELLIGENCE_EVENTS_LIMIT)
