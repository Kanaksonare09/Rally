"""
NotificationService: the one place that creates a Notification row.
Every caller (alerts/service.py, sos/service.py, app/api/trips.py,
group_service.py) goes through `notify()`/`notify_group()` rather than
constructing `Notification` directly, so the dedup rule below is applied
uniformly everywhere.

Channels: IN_APP is fully implemented (a Postgres row a user reads via
GET /notifications). PUSH is architecture-ready but not implemented —
`channel` exists on the model and `notify()`'s docstring notes exactly
where a push-delivery call would go, but nothing sends one yet (no device
token storage, no APNs/FCM integration — out of scope for this phase).

Failure isolation: every call site that triggers a notification wraps it
in try/except (or calls the `_safe` wrappers below) — a notification
failure must never break the alert/SOS/trip-lifecycle operation that
triggered it, the same "derived data, never load-bearing" rule
app/analytics/snapshot.py follows for analytics snapshots.
"""

import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List, Optional

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.errors import AppHTTPException
from app.models.enums import MemberStatus
from app.models.group_member import GroupMember
from app.models.notification import Notification

logger = logging.getLogger("rally.notifications")


def _active_group_member_ids_sync(db: Session, group_id: uuid.UUID) -> List[uuid.UUID]:
    """The one shared copy of "who's currently in this group" used by
    every notification fan-out (alerts, SOS, trip lifecycle, membership
    changes) — every other package in this backend keeps its own local
    copy of this same query for its own purposes (see e.g.
    app/route/service.py, app/websocket/handlers.py); this is the
    version specifically for "who should be notified."""
    return list(
        db.scalars(
            select(GroupMember.user_id).where(GroupMember.group_id == group_id, GroupMember.status == MemberStatus.ACTIVE)
        ).all()
    )


def notify(
    db: Session,
    *,
    user_id: uuid.UUID,
    type: str,
    title: str,
    message: str,
    severity: str = "INFO",
    trip_id: Optional[uuid.UUID] = None,
    dedup_key: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> Optional[Notification]:
    """Creates one notification, or silently does nothing if `dedup_key`
    is set and a notification with that exact (user_id, dedup_key) pair
    already exists — see the partial unique index on the model. Returns
    None on a deduplicated call (not an error), the created row
    otherwise.

    `dedup_key` should identify the *source occurrence*, not just the
    type — e.g. `f"alert:{alert.id}"` or `f"member_joined:{group_id}:
    {new_member_id}"` — so a genuinely new occurrence of the same TYPE
    (a second, later FALLING_BEHIND alert) still creates its own
    notification; only a retry/duplicate delivery of the SAME occurrence
    is suppressed.
    """
    notification = Notification(
        user_id=user_id,
        trip_id=trip_id,
        type=type,
        title=title,
        message=message,
        severity=severity,
        dedup_key=dedup_key,
        notification_metadata=metadata or {},
    )
    db.add(notification)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        return None
    db.refresh(notification)
    return notification


def notify_many(
    db: Session,
    *,
    user_ids: Iterable[uuid.UUID],
    type: str,
    title: str,
    message: str,
    severity: str = "INFO",
    trip_id: Optional[uuid.UUID] = None,
    dedup_key_fn=None,
    metadata: Optional[Dict[str, Any]] = None,
) -> List[Notification]:
    """notify() fanned out to several users at once (e.g. every active
    group member for a trip-started/group-level alert). `dedup_key_fn`,
    if given, is called as `dedup_key_fn(user_id)` — needed because a
    dedup key that's meant to be per-user must actually vary per user,
    not reuse the same string for everyone (which would make every user
    after the first a no-op)."""
    created = []
    for user_id in user_ids:
        dedup_key = dedup_key_fn(user_id) if dedup_key_fn else None
        result = notify(
            db, user_id=user_id, type=type, title=title, message=message, severity=severity,
            trip_id=trip_id, dedup_key=dedup_key, metadata=metadata,
        )
        if result is not None:
            created.append(result)
    return created


def notify_safely(db: Session, **kwargs) -> Optional[Notification]:
    """notify(), with any failure logged and swallowed — see the module
    docstring's failure-isolation rule. Use this from every call site
    that isn't already inside its own broad try/except."""
    try:
        return notify(db, **kwargs)
    except Exception:
        logger.exception("Failed to create notification (type=%s, user_id=%s)", kwargs.get("type"), kwargs.get("user_id"))
        return None


def notify_many_safely(db: Session, **kwargs) -> List[Notification]:
    try:
        return notify_many(db, **kwargs)
    except Exception:
        logger.exception("Failed to create notifications (type=%s)", kwargs.get("type"))
        return []


def notify_group_safely(
    db: Session,
    *,
    group_id: uuid.UUID,
    type: str,
    title: str,
    message: str,
    severity: str = "INFO",
    trip_id: Optional[uuid.UUID] = None,
    dedup_key_fn=None,
    metadata: Optional[Dict[str, Any]] = None,
    exclude_user_id: Optional[uuid.UUID] = None,
) -> List[Notification]:
    """notify_many_safely(), fanned out to every active member of
    `group_id` — the one entry point app/alerts/service.py,
    app/sos/service.py, app/api/trips.py, and app/services/group_service.py
    all use for "tell the group about this," so the membership query and
    failure-isolation behavior live in exactly one place."""
    try:
        member_ids = _active_group_member_ids_sync(db, group_id)
        if exclude_user_id is not None:
            member_ids = [uid for uid in member_ids if uid != exclude_user_id]
        return notify_many(
            db, user_ids=member_ids, type=type, title=title, message=message, severity=severity,
            trip_id=trip_id, dedup_key_fn=dedup_key_fn, metadata=metadata,
        )
    except Exception:
        logger.exception("Failed to create group notifications (type=%s, group_id=%s)", type, group_id)
        return []


# ---- REST-facing reads/writes ----------------------------------------------


def list_notifications(
    db: Session, user_id: uuid.UUID, *, unread_only: bool = False, limit: int = 20, offset: int = 0
) -> List[Notification]:
    stmt = select(Notification).where(Notification.user_id == user_id)
    if unread_only:
        stmt = stmt.where(Notification.read_at.is_(None))
    stmt = stmt.order_by(Notification.created_at.desc()).limit(limit).offset(offset)
    return list(db.scalars(stmt).all())


def count_notifications(db: Session, user_id: uuid.UUID, *, unread_only: bool = False) -> int:
    stmt = select(func.count()).select_from(Notification).where(Notification.user_id == user_id)
    if unread_only:
        stmt = stmt.where(Notification.read_at.is_(None))
    return db.scalar(stmt) or 0


def get_unread_count(db: Session, user_id: uuid.UUID) -> int:
    return count_notifications(db, user_id, unread_only=True)


def get_notification_for_user(db: Session, notification_id: uuid.UUID, user_id: uuid.UUID) -> Notification:
    """Same "same 404 whether it doesn't exist or isn't yours" pattern as
    every other ownership check in this backend — never reveals that a
    notification id belongs to someone else."""
    notification = db.get(Notification, notification_id)
    if notification is None or notification.user_id != user_id:
        raise AppHTTPException(status_code=404, code="NOTIFICATION_NOT_FOUND", detail="Notification not found.")
    return notification


def mark_read(db: Session, notification: Notification) -> Notification:
    if notification.read_at is None:
        notification.read_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(notification)
    return notification


def mark_all_read(db: Session, user_id: uuid.UUID) -> int:
    """Returns how many were actually marked (already-read notifications
    aren't re-touched)."""
    stmt = select(Notification).where(Notification.user_id == user_id, Notification.read_at.is_(None))
    unread = list(db.scalars(stmt).all())
    now = datetime.now(timezone.utc)
    for notification in unread:
        notification.read_at = now
    db.commit()
    return len(unread)
