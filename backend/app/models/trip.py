import uuid
from datetime import datetime
from typing import Optional

from geoalchemy2 import Geography
from sqlalchemy import DateTime, Enum as SQLEnum, Float, ForeignKey, Index, Integer, String, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.enums import TripStatus
from app.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin


class Trip(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "trips"
    __table_args__ = (
        Index("ix_trips_created_at", "created_at"),
        # Group trip history (GET /groups/{group_id}/trips, Phase 10) always
        # filters by group_id and sorts by created_at — this composite
        # index serves that ordering directly instead of a sort-then-scan.
        Index("ix_trips_group_created", "group_id", "created_at"),
        # Enforces "at most one ACTIVE trip per group" at the database level
        # so two concurrent requests can't both succeed — see trip_service.
        Index(
            "uq_trips_one_active_per_group",
            "group_id",
            unique=True,
            postgresql_where=text("status = 'ACTIVE'"),
        ),
    )

    # RESTRICT, not CASCADE: a group must not be deletable while it still has
    # trip history attached. Deleting historical data has to be an explicit,
    # separate action — never a side effect of removing a group.
    group_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("groups.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    started_by: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("profiles.id", ondelete="SET NULL"), nullable=True, index=True
    )
    status: Mapped[TripStatus] = mapped_column(
        SQLEnum(TripStatus, name="trip_status"), default=TripStatus.CREATED, nullable=False, index=True
    )
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    ended_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    destination_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    start_location = mapped_column(Geography(geometry_type="POINT", srid=4326), nullable=True)
    destination = mapped_column(Geography(geometry_type="POINT", srid=4326), nullable=True)
    distance: Mapped[Optional[float]] = mapped_column(Float, nullable=True)  # kilometers
    duration: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)  # minutes
    safety_score: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)  # 0-100

    group: Mapped["Group"] = relationship(back_populates="trips")  # noqa: F821
    # Trips are protected from casual group deletion (see group_id above);
    # once a trip itself is explicitly deleted, its child records go with it.
    location_history: Mapped[list["LocationHistory"]] = relationship(  # noqa: F821
        back_populates="trip", cascade="all, delete-orphan"
    )
    alerts: Mapped[list["Alert"]] = relationship(back_populates="trip", cascade="all, delete-orphan")  # noqa: F821
    sos_events: Mapped[list["SOSEvent"]] = relationship(  # noqa: F821
        back_populates="trip", cascade="all, delete-orphan"
    )
