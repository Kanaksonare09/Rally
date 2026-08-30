"""trip_analytics_snapshots: Phase 10 analytics + trip history + dashboard

Revision ID: 0006
Revises: 0005
Create Date: 2026-08-30

Adds the `trip_analytics_snapshots` table (a frozen, derived summary of a
COMPLETED trip's headline analytics — see app/models/trip_analytics_snapshot.py)
and one composite index on `trips` that the new group trip history query
pattern justifies (group_id + created_at ordering). Every other Phase 10
read (member/route/safety analytics, timeline) aggregates the existing
location_history/routes/intelligence_events/alerts/sos_events tables
in place — nothing else about their shape changes in this migration.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0006"
down_revision: Union[str, None] = "0005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "trip_analytics_snapshots",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("trip_id", postgresql.UUID(as_uuid=True), nullable=False, unique=True),
        sa.Column("duration_seconds", sa.Integer(), nullable=True),
        sa.Column("distance_traveled_meters", sa.Float(), nullable=True),
        sa.Column("planned_distance_meters", sa.Float(), nullable=True),
        sa.Column("completion_percent", sa.Float(), nullable=True),
        sa.Column("member_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("alerts_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("critical_alerts_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("sos_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("route_deviations", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("generated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["trip_id"], ["trips.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_trip_analytics_snapshots_trip_id", "trip_analytics_snapshots", ["trip_id"], unique=True)

    # Group trip history (GET /groups/{group_id}/trips) always filters by
    # group_id and sorts by created_at — this composite index serves that
    # directly, on top of the existing single-column group_id/created_at
    # indexes from earlier migrations.
    op.create_index("ix_trips_group_created", "trips", ["group_id", "created_at"])


def downgrade() -> None:
    op.drop_index("ix_trips_group_created", table_name="trips")
    op.drop_index("ix_trip_analytics_snapshots_trip_id", table_name="trip_analytics_snapshots")
    op.drop_table("trip_analytics_snapshots")
