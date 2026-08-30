import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, Float, ForeignKey, Integer
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.mixins import UUIDPrimaryKeyMixin, utc_now


class TripAnalyticsSnapshot(UUIDPrimaryKeyMixin, Base):
    """A frozen copy of a COMPLETED trip's headline analytics, generated
    once when the trip ends (see app/analytics/snapshot.py, hooked into
    app/api/trips.py's end_trip_endpoint). Purely derived data — every
    field here is recomputable from location_history/routes/
    intelligence_events/alerts/sos_events, which remain the source of
    truth. This table exists only so a completed trip's dashboard/history
    doesn't recompute the same aggregation on every request.

    `trip_id` is UNIQUE: at most one snapshot per trip, enforced at the
    database level (not just an app-level check) so a retried/concurrent
    "generate on trip end" call can never produce two rows — see
    generate_snapshot()'s "get existing or create" logic.

    Every numeric field mirrors the zero-vs-null contract used throughout
    Phase 10: `None` means "could not be calculated" (e.g. no GPS data, no
    route), never a fabricated 0.
    """

    __tablename__ = "trip_analytics_snapshots"

    trip_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("trips.id", ondelete="CASCADE"), nullable=False, unique=True, index=True
    )

    duration_seconds: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    distance_traveled_meters: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    planned_distance_meters: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    completion_percent: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    member_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    alerts_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    critical_alerts_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    sos_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    route_deviations: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    generated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
