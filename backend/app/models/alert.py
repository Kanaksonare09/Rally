import uuid
from datetime import datetime
from typing import Optional

from geoalchemy2 import Geography
from sqlalchemy import DateTime, Enum as SQLEnum, ForeignKey, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.enums import AlertSeverity, AlertStatus, AlertType
from app.models.mixins import UUIDPrimaryKeyMixin, utc_now


class Alert(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "alerts"

    group_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("groups.id", ondelete="CASCADE"), nullable=False, index=True
    )
    trip_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("trips.id", ondelete="CASCADE"), nullable=False, index=True
    )
    # Nullable: some alert types (e.g. GROUP_SEPARATION) can describe the
    # group as a whole rather than one specific member.
    user_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("profiles.id", ondelete="SET NULL"), nullable=True
    )

    type: Mapped[AlertType] = mapped_column(SQLEnum(AlertType, name="alert_type"), nullable=False)
    severity: Mapped[AlertSeverity] = mapped_column(
        SQLEnum(AlertSeverity, name="alert_severity"), nullable=False
    )
    message: Mapped[str] = mapped_column(Text, nullable=False)
    location = mapped_column(Geography(geometry_type="POINT", srid=4326), nullable=True)
    status: Mapped[AlertStatus] = mapped_column(
        SQLEnum(AlertStatus, name="alert_status"), default=AlertStatus.ACTIVE, nullable=False
    )

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    resolved_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    trip: Mapped["Trip"] = relationship(back_populates="alerts")  # noqa: F821
