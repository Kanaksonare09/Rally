import uuid
from datetime import datetime
from typing import Any, Dict, Optional

from pydantic import BaseModel, Field

from app.models.enums import AlertSeverity, AlertStatus, AlertType

DEFAULT_ALERTS_LIMIT = 100
MAX_ALERTS_LIMIT = 1000


class AlertResponse(BaseModel):
    id: uuid.UUID
    trip_id: uuid.UUID
    event_id: Optional[uuid.UUID] = None
    alert_type: AlertType
    severity: AlertSeverity
    status: AlertStatus
    title: str
    message: str
    user_id: Optional[uuid.UUID] = None
    related_user_id: Optional[uuid.UUID] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)
    created_at: datetime
    acknowledged_at: Optional[datetime] = None
    resolved_at: Optional[datetime] = None


class AlertQuery(BaseModel):
    status: Optional[AlertStatus] = None
    severity: Optional[AlertSeverity] = None
    alert_type: Optional[AlertType] = None
    user_id: Optional[uuid.UUID] = None
    from_time: Optional[datetime] = None
    to_time: Optional[datetime] = None
    limit: int = Field(DEFAULT_ALERTS_LIMIT, ge=1, le=MAX_ALERTS_LIMIT)
