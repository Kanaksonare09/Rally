"""intelligence_events: raw detections from the intelligence engine
(Phase 7) - distinct from the future alerts table (Phase 8)

Revision ID: 0003
Revises: 0002
Create Date: 2026-08-30

Hand-written, same reasoning as 0001/0002 — no live Supabase connection to
autogenerate against. Mirrors app/models/intelligence_event.py.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from geoalchemy2 import Geography
from sqlalchemy.dialects import postgresql

revision: str = "0003"
down_revision: Union[str, None] = "0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "intelligence_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("group_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("trip_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "event_type",
            sa.Enum(
                "FALLING_BEHIND",
                "GROUP_SEPARATION",
                "UNEXPECTED_STOP",
                "SPEED_ANOMALY",
                "ISOLATED_MEMBER",
                "MOVING_TOGETHER",
                "STOPPED",
                "MOVING",
                name="intelligence_event_type",
            ),
            nullable=False,
        ),
        sa.Column(
            "severity",
            sa.Enum("INFO", "WARNING", "CRITICAL", name="intelligence_severity"),
            nullable=False,
        ),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("related_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("latitude", sa.Float(), nullable=True),
        sa.Column("longitude", sa.Float(), nullable=True),
        sa.Column("location", Geography(geometry_type="POINT", srid=4326), nullable=True),
        sa.Column("event_metadata", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column("detected_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["group_id"], ["groups.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["trip_id"], ["trips.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["profiles.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["related_user_id"], ["profiles.id"], ondelete="SET NULL"),
    )

    op.create_index("ix_intelligence_events_group_id", "intelligence_events", ["group_id"])
    op.create_index("ix_intelligence_events_trip_id", "intelligence_events", ["trip_id"])
    op.create_index("ix_intelligence_events_event_type", "intelligence_events", ["event_type"])
    op.create_index("ix_intelligence_events_user_id", "intelligence_events", ["user_id"])
    op.create_index("ix_intelligence_events_trip_type", "intelligence_events", ["trip_id", "event_type"])
    op.create_index("ix_intelligence_events_trip_created", "intelligence_events", ["trip_id", "created_at"])

    # Database-level guarantee that two concurrent evaluations can't both
    # insert an active event for the same (trip, event_type, user) — the
    # same partial-unique-index technique as trips' one-active-trip rule.
    op.create_index(
        "uq_intelligence_events_one_active_per_subject",
        "intelligence_events",
        ["trip_id", "event_type", "user_id"],
        unique=True,
        postgresql_where=sa.text("resolved_at IS NULL"),
    )


def downgrade() -> None:
    op.drop_table("intelligence_events")
    op.execute("DROP TYPE IF EXISTS intelligence_severity")
    op.execute("DROP TYPE IF EXISTS intelligence_event_type")
