"""alerts + sos_events: Phase 8 alert engine and SOS emergency system

Revision ID: 0004
Revises: 0003
Create Date: 2026-08-30

`alerts` is dropped and recreated rather than altered in place: it was
created in 0001 as an unused placeholder (never wired to any code before
this phase) with a materially different shape (alert_type/severity/status
enum values, no event_id/title/metadata/acknowledged_at) — there is no
data to preserve. `sos_events` already had real fields worth keeping, so
it's altered additively instead.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from geoalchemy2 import Geography
from sqlalchemy.dialects import postgresql

revision: str = "0004"
down_revision: Union[str, None] = "0003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # --- alerts: drop the unused Phase 1 placeholder, recreate to spec ---
    op.drop_table("alerts")
    op.execute("DROP TYPE IF EXISTS alert_type")
    op.execute("DROP TYPE IF EXISTS alert_severity")
    op.execute("DROP TYPE IF EXISTS alert_status")

    op.create_table(
        "alerts",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("group_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("trip_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("event_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "alert_type",
            sa.Enum(
                "FALLING_BEHIND", "GROUP_SEPARATION", "ISOLATED_MEMBER", "UNEXPECTED_STOP", "SPEED_ANOMALY",
                name="alert_type",
            ),
            nullable=False,
        ),
        sa.Column("severity", sa.Enum("INFO", "WARNING", "CRITICAL", name="alert_severity"), nullable=False),
        sa.Column(
            "status",
            sa.Enum("ACTIVE", "ACKNOWLEDGED", "RESOLVED", name="alert_status"),
            nullable=False,
            server_default="ACTIVE",
        ),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("related_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("location", Geography(geometry_type="POINT", srid=4326), nullable=True),
        sa.Column("alert_metadata", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("acknowledged_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["group_id"], ["groups.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["trip_id"], ["trips.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["event_id"], ["intelligence_events.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["user_id"], ["profiles.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["related_user_id"], ["profiles.id"], ondelete="SET NULL"),
    )
    op.create_index("ix_alerts_group_id", "alerts", ["group_id"])
    op.create_index("ix_alerts_trip_id", "alerts", ["trip_id"])
    op.create_index("ix_alerts_event_id", "alerts", ["event_id"])
    op.create_index("ix_alerts_user_id", "alerts", ["user_id"])
    op.create_index("ix_alerts_status", "alerts", ["status"])
    op.create_index("ix_alerts_alert_type", "alerts", ["alert_type"])
    op.create_index("ix_alerts_trip_created", "alerts", ["trip_id", "created_at"])
    # One unresolved (ACTIVE or ACKNOWLEDGED) alert per intelligence event
    # — the actual dedup guarantee, not just an application-level check.
    op.create_index(
        "uq_alerts_one_unresolved_per_event",
        "alerts",
        ["event_id"],
        unique=True,
        postgresql_where=sa.text("resolved_at IS NULL"),
    )

    # --- sos_events: additive changes only, existing rows (if any) keep working ---
    op.execute("ALTER TYPE sos_status ADD VALUE IF NOT EXISTS 'ACKNOWLEDGED'")

    op.add_column("sos_events", sa.Column("latitude", sa.Float(), nullable=True))
    op.add_column("sos_events", sa.Column("longitude", sa.Float(), nullable=True))
    op.add_column("sos_events", sa.Column("accuracy", sa.Float(), nullable=True))
    op.add_column("sos_events", sa.Column("message", sa.Text(), nullable=True))
    op.add_column("sos_events", sa.Column("sos_metadata", postgresql.JSONB(), nullable=False, server_default="{}"))
    op.add_column("sos_events", sa.Column("acknowledged_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column(
        "sos_events",
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    # latitude/longitude were added nullable to allow this migration to run
    # against a table that might already have rows (only geography
    # `location` was required before) — backfill from the existing
    # geography column, then tighten to NOT NULL to match the model.
    op.execute(
        "UPDATE sos_events SET latitude = ST_Y(location::geometry), longitude = ST_X(location::geometry) "
        "WHERE latitude IS NULL"
    )
    op.alter_column("sos_events", "latitude", nullable=False)
    op.alter_column("sos_events", "longitude", nullable=False)

    op.create_index("ix_sos_events_user_id", "sos_events", ["user_id"])
    op.create_index("ix_sos_events_status", "sos_events", ["status"])
    op.create_index("ix_sos_events_trip_triggered", "sos_events", ["trip_id", "triggered_at"])


def downgrade() -> None:
    op.drop_index("ix_sos_events_trip_triggered", table_name="sos_events")
    op.drop_index("ix_sos_events_status", table_name="sos_events")
    op.drop_index("ix_sos_events_user_id", table_name="sos_events")
    op.drop_column("sos_events", "created_at")
    op.drop_column("sos_events", "acknowledged_at")
    op.drop_column("sos_events", "sos_metadata")
    op.drop_column("sos_events", "message")
    op.drop_column("sos_events", "accuracy")
    op.drop_column("sos_events", "longitude")
    op.drop_column("sos_events", "latitude")
    # Postgres cannot remove a single enum value — 'ACKNOWLEDGED' stays in
    # sos_status even on downgrade; harmless if unused.

    op.drop_table("alerts")
    op.execute("DROP TYPE IF EXISTS alert_status")
    op.execute("DROP TYPE IF EXISTS alert_severity")
    op.execute("DROP TYPE IF EXISTS alert_type")
