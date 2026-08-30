import uuid
from datetime import datetime
from typing import Any, Dict, Optional

from geoalchemy2 import Geography
from sqlalchemy import DateTime, Enum as SQLEnum, Float, ForeignKey, Index
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.enums import IntelligenceEventType, IntelligenceSeverity
from app.models.mixins import UUIDPrimaryKeyMixin, utc_now


class IntelligenceEvent(UUIDPrimaryKeyMixin, Base):
    """A detection from the intelligence engine (app/intelligence/) — raw
    signal, not a user-facing alert. The Phase 8 alert engine will read
    these to decide whether/how to notify anyone; this table only records
    what was detected and when.

    Lifecycle is `resolved_at IS NULL` = active, non-null = resolved — no
    separate status column (same pattern as Alert). The partial unique
    index below is what actually prevents duplicate active events for the
    same (trip, event_type, user) — the same "one ACTIVE trip per group"
    technique from Phase 4, applied here to stop concurrent evaluations
    from double-inserting.
    """

    __tablename__ = "intelligence_events"
    __table_args__ = (
        Index("ix_intelligence_events_trip_type", "trip_id", "event_type"),
        Index("ix_intelligence_events_trip_created", "trip_id", "created_at"),
        # NULLS are not equal to each other in a unique index, so this only
        # constrains the *active* rows for a given (trip, type, user) —
        # resolved history can have as many rows as it wants. user_id can
        # itself be NULL (group-level events), which Postgres also treats
        # as distinct per row unless coalesced — acceptable here since a
        # concurrent double-insert race matters most for per-user events;
        # group-level dedup is additionally guarded by the Redis lock in
        # app/intelligence/engine.py.
        Index(
            "uq_intelligence_events_one_active_per_subject",
            "trip_id",
            "event_type",
            "user_id",
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

    event_type: Mapped[IntelligenceEventType] = mapped_column(
        SQLEnum(IntelligenceEventType, name="intelligence_event_type"), nullable=False, index=True
    )
    severity: Mapped[IntelligenceSeverity] = mapped_column(
        SQLEnum(IntelligenceSeverity, name="intelligence_severity"), nullable=False
    )

    # The member this event is about (falling behind, stopped, speed
    # anomaly...). NULL for group-level events (GROUP_SEPARATION as a
    # whole, MOVING_TOGETHER).
    user_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("profiles.id", ondelete="SET NULL"), nullable=True, index=True
    )
    # A second member the event is relative to, where relevant (e.g. the
    # nearest other member for an ISOLATED_MEMBER event). Optional, purely
    # informational.
    related_user_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("profiles.id", ondelete="SET NULL"), nullable=True
    )

    latitude: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    longitude: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    location = mapped_column(Geography(geometry_type="POINT", srid=4326), nullable=True)

    # Event-type-specific detail (distance_meters, threshold_meters,
    # observed_speed, duration_seconds, ...) — deliberately not modeled as
    # dedicated columns since every event type needs different fields.
    event_metadata: Mapped[Dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)

    detected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    resolved_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
