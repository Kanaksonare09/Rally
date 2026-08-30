"""routes: Phase 9 route intelligence + navigation foundation

Revision ID: 0005
Revises: 0004
Create Date: 2026-08-30

Adds the `routes` table (one planned route per trip — routes.trip_id is
UNIQUE) and additively extends the two existing enums that now have a
route-related member: intelligence_event_type gains ROUTE_DEVIATION (the
one route-related type that persists as a real intelligence_events row —
see app/intelligence/detectors.py::detect_route_deviation) and alert_type
gains the matching ROUTE_DEVIATION alert policy entry
(app/alerts/policies.py). Both are additive (`ADD VALUE IF NOT EXISTS`),
unlike 0004's `alerts` table rebuild — both tables have real shipped data
by this point, so there is no placeholder to safely drop and recreate.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from geoalchemy2 import Geometry
from sqlalchemy.dialects import postgresql

revision: str = "0005"
down_revision: Union[str, None] = "0004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TYPE intelligence_event_type ADD VALUE IF NOT EXISTS 'ROUTE_DEVIATION'")
    op.execute("ALTER TYPE alert_type ADD VALUE IF NOT EXISTS 'ROUTE_DEVIATION'")

    op.create_table(
        "routes",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("trip_id", postgresql.UUID(as_uuid=True), nullable=False, unique=True),
        sa.Column("name", sa.String(length=255), nullable=True),
        sa.Column("origin_latitude", sa.Float(), nullable=False),
        sa.Column("origin_longitude", sa.Float(), nullable=False),
        sa.Column("destination_latitude", sa.Float(), nullable=False),
        sa.Column("destination_longitude", sa.Float(), nullable=False),
        sa.Column("geometry", Geometry(geometry_type="LINESTRING", srid=4326), nullable=False),
        # GeoJSON-order [longitude, latitude] pairs — the copy
        # app/route/matcher.py actually reads for live matching. See
        # app/models/route.py's docstring for why this duplicates `geometry`
        # rather than one being derived from the other at read time.
        sa.Column("coordinates", postgresql.JSONB(), nullable=False),
        # Server-calculated (Haversine sum over `coordinates`) at creation
        # time — never trusted from the client.
        sa.Column("distance_meters", sa.Float(), nullable=False),
        sa.Column("estimated_duration_seconds", sa.Integer(), nullable=True),
        sa.Column(
            "status",
            sa.Enum("PLANNED", "ACTIVE", "COMPLETED", "CANCELLED", name="route_status"),
            nullable=False,
            server_default="PLANNED",
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["trip_id"], ["trips.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_routes_trip_id", "routes", ["trip_id"], unique=True)
    op.create_index("ix_routes_status", "routes", ["status"])
    op.create_index("ix_routes_trip_status", "routes", ["trip_id", "status"])


def downgrade() -> None:
    op.drop_index("ix_routes_trip_status", table_name="routes")
    op.drop_index("ix_routes_status", table_name="routes")
    op.drop_index("ix_routes_trip_id", table_name="routes")
    op.drop_table("routes")
    op.execute("DROP TYPE IF EXISTS route_status")
    # Postgres cannot remove a single enum value — ROUTE_DEVIATION stays in
    # intelligence_event_type/alert_type even on downgrade; harmless if
    # unused (same accepted limitation as 0004's sos_status ACKNOWLEDGED
    # addition).
