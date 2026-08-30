import uuid
from datetime import datetime
from typing import Any, Dict, Optional

from sqlalchemy import DateTime, ForeignKey, Index, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.mixins import UUIDPrimaryKeyMixin, utc_now


class Notification(UUIDPrimaryKeyMixin, Base):
    """An IN_APP notification for one user (see app/notifications/service.py
    — the only writer). `channel` exists on the row even though this phase
    only ever writes `"IN_APP"`, so a future PUSH implementation is a new
    delivery path against the same record, not a schema change.

    `dedup_key` is how a repeatedly-firing source (a FALLING_BEHIND alert
    still active on the next evaluation tick, say) doesn't spam a user
    with duplicate notifications — see the partial unique index below and
    NotificationService.notify()'s "insert, ignore IntegrityError" logic.
    NULL dedup_key means "always create a new row" (used for one-off
    events like TRIP_STARTED that never repeat for the same trip).
    """

    __tablename__ = "notifications"
    __table_args__ = (
        Index("ix_notifications_user_created", "user_id", "created_at"),
        Index("ix_notifications_user_read", "user_id", "read_at"),
        # At most one notification per (user, dedup_key) — the actual
        # duplicate-prevention guarantee, not just an application-level
        # check (same partial-unique-index technique used throughout this
        # backend, e.g. the one active trip/alert/SOS rules).
        Index(
            "uq_notifications_user_dedup_key",
            "user_id",
            "dedup_key",
            unique=True,
            postgresql_where="dedup_key IS NOT NULL",
        ),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("profiles.id", ondelete="CASCADE"), nullable=False, index=True
    )
    # Nullable: not every notification is trip-scoped (none currently
    # aren't, but the column isn't artificially forced NOT NULL for a
    # future non-trip notification type).
    trip_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("trips.id", ondelete="CASCADE"), nullable=True, index=True
    )

    type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    # Plain string, not a shared enum with AlertSeverity/IntelligenceSeverity
    # — a notification's severity is a presentation concern (how the
    # frontend styles it), not itself a safety classification.
    severity: Mapped[str] = mapped_column(String(20), nullable=False, default="INFO")

    dedup_key: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    notification_metadata: Mapped[Dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)

    read_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
