import uuid
from datetime import datetime
from typing import Any, Dict, Optional

from geoalchemy2 import Geography
from sqlalchemy import DateTime, Enum as SQLEnum, ForeignKey, Index, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.enums import AlertSeverity, AlertStatus, AlertType
from app.models.mixins import UUIDPrimaryKeyMixin, utc_now


class Alert(UUIDPrimaryKeyMixin, Base):
    """A user-facing notification, decided by the Alert Engine
    (app/alerts/) from a Phase 7 intelligence_event — never created
    directly by a detector. `resolved_at IS NULL` = not yet resolved
    (ACTIVE or ACKNOWLEDGED); `status` still exists as its own column
    (unlike IntelligenceEvent) because there's a real middle state to
    track between "active" and "resolved"."""

    __tablename__ = "alerts"
    __table_args__ = (
        Index("ix_alerts_trip_created", "trip_id", "created_at"),
        # The actual "don't create 100 alerts for one ongoing condition"
        # guarantee: at most one unresolved alert per intelligence event,
        # enforced at the database level regardless of evaluation races.
        Index(
            "uq_alerts_one_unresolved_per_event",
            "event_id",
            unique=True,
            postgresql_where="resolved_at IS NULL",
        ),
    )

    group_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("groups.id", ondelete="CASCADE"), nullable=False, index=True
    )
    trip_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("trips.id", ondelete="CASCADE"), nullable=False, index=True
    )
    # The intelligence_events row this alert was decided from. Nullable
    # because the FK uses SET NULL (the alert — a user-facing record —
    # must outlive its source detection being cleaned up), but in
    # practice every alert created by app/alerts/service.py has one.
    event_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("intelligence_events.id", ondelete="SET NULL"), nullable=True, index=True
    )

    alert_type: Mapped[AlertType] = mapped_column(SQLEnum(AlertType, name="alert_type"), nullable=False, index=True)
    severity: Mapped[AlertSeverity] = mapped_column(SQLEnum(AlertSeverity, name="alert_severity"), nullable=False)
    status: Mapped[AlertStatus] = mapped_column(
        SQLEnum(AlertStatus, name="alert_status"), default=AlertStatus.ACTIVE, nullable=False, index=True
    )

    # The member the alert is about (falling behind, stopped...). NULL for
    # group-level alerts (GROUP_SEPARATION).
    user_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("profiles.id", ondelete="SET NULL"), nullable=True, index=True
    )
    related_user_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("profiles.id", ondelete="SET NULL"), nullable=True
    )

    title: Mapped[str] = mapped_column(Text, nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    location = mapped_column(Geography(geometry_type="POINT", srid=4326), nullable=True)
    # Copied from the source intelligence_event's metadata at creation
    # time — deliberately not re-derived live, so an alert's detail stays
    # a stable record of what triggered it even as the trip continues.
    alert_metadata: Mapped[Dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    acknowledged_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    resolved_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    trip: Mapped["Trip"] = relationship(back_populates="alerts")  # noqa: F821
