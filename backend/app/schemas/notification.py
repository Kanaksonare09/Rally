import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict

DEFAULT_NOTIFICATION_LIMIT = 20
MAX_NOTIFICATION_LIMIT = 100


class NotificationItem(BaseModel):
    id: uuid.UUID
    trip_id: Optional[uuid.UUID] = None
    type: str
    title: str
    message: str
    severity: str
    metadata: Dict[str, Any]
    read_at: Optional[datetime] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class NotificationListResponse(BaseModel):
    items: List[NotificationItem]
    total: int
    unread_count: int
    limit: int
    offset: int


class UnreadCountResponse(BaseModel):
    unread_count: int


class MarkAllReadResponse(BaseModel):
    marked_count: int
