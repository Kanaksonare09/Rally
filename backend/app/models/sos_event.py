import uuid
from datetime import datetime
from typing import Any, Dict, Optional

from geoalchemy2 import Geography
from sqlalchemy import DateTime, Enum as SQLEnum, Float, ForeignKey, Index, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.enums import SOSStatus
from app.models.mixins import UUIDPrimaryKeyMixin, utc_now


class SOSEvent(UUIDPrimaryKeyMixin, Base):
    """An explicitly user-triggered emergency — never created by the
    intelligence/alert engines (see app/sos/service.py's module docstring
    for the ALERT vs SOS distinction). The trigger location is captured
    once and is immutable thereafter; nothing about this row's location
    fields is ever overwritten by a later GPS update."""

    __tablename__ = "sos_events"
    __table_args__ = (Index("ix_sos_events_trip_triggered", "trip_id", "triggered_at"),)

    group_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("groups.id", ondelete="CASCADE"), nullable=False, index=True
    )
    trip_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("trips.id", ondelete="CASCADE"), nullable=False, index=True
    )
    # SET NULL, not CASCADE: the record that an emergency happened must
    # survive even if we later lose the reference to who triggered it.
    user_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("profiles.id", ondelete="SET NULL"), nullable=True, index=True
    )

    latitude: Mapped[float] = mapped_column(Float, nullable=False)
    longitude: Mapped[float] = mapped_column(Float, nullable=False)
    accuracy: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    location = mapped_column(Geography(geometry_type="POINT", srid=4326), nullable=False)

    status: Mapped[SOSStatus] = mapped_column(
        SQLEnum(SOSStatus, name="sos_status"), default=SOSStatus.ACTIVE, nullable=False, index=True
    )
    message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    sos_metadata: Mapped[Dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)

    triggered_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    acknowledged_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    resolved_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)

    trip: Mapped["Trip"] = relationship(back_populates="sos_events")  # noqa: F821
