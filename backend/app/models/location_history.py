import uuid
from datetime import datetime
from typing import Optional

from geoalchemy2 import Geography
from sqlalchemy import DateTime, Float, ForeignKey, Index
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.mixins import UUIDPrimaryKeyMixin, utc_now


class LocationHistory(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "location_history"
    __table_args__ = (
        Index("ix_location_history_trip_recorded", "trip_id", "recorded_at"),
        Index("ix_location_history_group_recorded", "group_id", "recorded_at"),
        Index("ix_location_history_user_recorded", "user_id", "recorded_at"),
    )

    trip_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("trips.id", ondelete="CASCADE"), nullable=False, index=True
    )
    group_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("groups.id", ondelete="CASCADE"), nullable=False, index=True
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("profiles.id", ondelete="CASCADE"), nullable=False, index=True
    )

    location = mapped_column(Geography(geometry_type="POINT", srid=4326), nullable=False)
    latitude: Mapped[float] = mapped_column(Float, nullable=False)
    longitude: Mapped[float] = mapped_column(Float, nullable=False)
    accuracy: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    speed: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    heading: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)

    trip: Mapped["Trip"] = relationship(back_populates="location_history")  # noqa: F821
