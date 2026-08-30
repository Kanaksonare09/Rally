import uuid
from datetime import datetime
from typing import Any, List, Optional

from geoalchemy2 import Geometry
from sqlalchemy import DateTime, Enum as SQLEnum, Float, ForeignKey, Index, Integer, String
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.enums import RouteStatus
from app.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin


class Route(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """The PLANNED path for a trip — deliberately separate from
    location_history (Phase 5, where users actually went). GPS updates
    never modify this row; only an explicit route-replace (while still
    PLANNED) or a trip-lifecycle transition (start/end/cancel, see
    app/route/service.py's activate/complete/cancel hooks) changes it.

    `coordinates` (JSONB) and `geometry` (PostGIS LINESTRING) store the
    same data twice, deliberately: `geometry` is a real spatial column —
    "prefer LINESTRING... do not store geometry as an arbitrary text
    blob" — available for external/future spatial queries against a live
    Postgres. `coordinates` is what app/route/matcher.py actually reads
    for live matching (Shapely + Haversine, in Python, against a cached
    list) — see that module's docstring for why live matching avoids a
    PostGIS round trip per GPS update. Both are written together at
    creation time from the same validated input; neither is ever the
    source of truth for the other.
    """

    __tablename__ = "routes"
    __table_args__ = (Index("ix_routes_trip_status", "trip_id", "status"),)

    # One route per trip — replacing a PLANNED route updates this same
    # row rather than creating a new one (see ROUTE VERSIONING: "do not
    # over-engineer" in this phase's spec).
    trip_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("trips.id", ondelete="CASCADE"), nullable=False, unique=True, index=True
    )
    name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    origin_latitude: Mapped[float] = mapped_column(Float, nullable=False)
    origin_longitude: Mapped[float] = mapped_column(Float, nullable=False)
    destination_latitude: Mapped[float] = mapped_column(Float, nullable=False)
    destination_longitude: Mapped[float] = mapped_column(Float, nullable=False)

    geometry = mapped_column(Geometry(geometry_type="LINESTRING", srid=4326), nullable=False)
    # GeoJSON-convention [longitude, latitude] pairs — see app/route/matcher.py.
    coordinates: Mapped[List[List[float]]] = mapped_column(JSONB, nullable=False)

    # Always server-calculated (Haversine sum over `coordinates`), never
    # trusted from the client — see app/route/service.py.
    distance_meters: Mapped[float] = mapped_column(Float, nullable=False)
    estimated_duration_seconds: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    status: Mapped[RouteStatus] = mapped_column(
        SQLEnum(RouteStatus, name="route_status"), default=RouteStatus.PLANNED, nullable=False, index=True
    )
