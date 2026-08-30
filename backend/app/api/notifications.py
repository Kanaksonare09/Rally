import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.dependencies.auth import get_current_user_id
from app.models.notification import Notification
from app.notifications import service as notification_service
from app.schemas.notification import (
    DEFAULT_NOTIFICATION_LIMIT,
    MAX_NOTIFICATION_LIMIT,
    MarkAllReadResponse,
    NotificationItem,
    NotificationListResponse,
    UnreadCountResponse,
)

router = APIRouter(tags=["Notifications"])


def _serialize(notification: Notification) -> NotificationItem:
    return NotificationItem(
        id=notification.id,
        trip_id=notification.trip_id,
        type=notification.type,
        title=notification.title,
        message=notification.message,
        severity=notification.severity,
        metadata=notification.notification_metadata,
        read_at=notification.read_at,
        created_at=notification.created_at,
    )


@router.get("/notifications", response_model=NotificationListResponse)
def list_notifications_endpoint(
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
    unread_only: bool = Query(False),
    limit: int = Query(DEFAULT_NOTIFICATION_LIMIT, ge=1, le=MAX_NOTIFICATION_LIMIT),
    offset: int = Query(0, ge=0),
):
    """The authenticated user's own notifications, newest first — the
    user id always comes from the verified token, never a query/body
    parameter, so there is no way to read another user's notifications."""
    uid = uuid.UUID(user_id)
    items = notification_service.list_notifications(db, uid, unread_only=unread_only, limit=limit, offset=offset)
    total = notification_service.count_notifications(db, uid, unread_only=unread_only)
    unread_count = notification_service.get_unread_count(db, uid)
    return NotificationListResponse(
        items=[_serialize(n) for n in items], total=total, unread_count=unread_count, limit=limit, offset=offset
    )


@router.get("/notifications/unread-count", response_model=UnreadCountResponse)
def get_unread_count_endpoint(
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    return UnreadCountResponse(unread_count=notification_service.get_unread_count(db, uuid.UUID(user_id)))


@router.patch("/notifications/{notification_id}/read", response_model=NotificationItem)
def mark_notification_read_endpoint(
    notification_id: uuid.UUID,
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    notification = notification_service.get_notification_for_user(db, notification_id, uuid.UUID(user_id))
    updated = notification_service.mark_read(db, notification)
    return _serialize(updated)


@router.patch("/notifications/read-all", response_model=MarkAllReadResponse)
def mark_all_notifications_read_endpoint(
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    marked = notification_service.mark_all_read(db, uuid.UUID(user_id))
    return MarkAllReadResponse(marked_count=marked)
