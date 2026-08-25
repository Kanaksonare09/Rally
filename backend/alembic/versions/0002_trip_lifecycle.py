"""trip lifecycle: destination_name column, lookup indexes, and the
one-active-trip-per-group constraint

Revision ID: 0002
Revises: 0001
Create Date: 2026-08-26

Hand-written, same reasoning as 0001 — no live Supabase connection to
autogenerate against. Mirrors app/models/trip.py.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0002"
down_revision: Union[str, None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("trips", sa.Column("destination_name", sa.String(length=255), nullable=True))

    op.create_index("ix_trips_status", "trips", ["status"])
    op.create_index("ix_trips_started_by", "trips", ["started_by"])
    op.create_index("ix_trips_created_at", "trips", ["created_at"])

    # Database-level guarantee that a group can have at most one ACTIVE
    # trip at a time — a partial unique index, not an app-level check, so
    # two concurrent "start trip" requests can't both succeed.
    op.create_index(
        "uq_trips_one_active_per_group",
        "trips",
        ["group_id"],
        unique=True,
        postgresql_where=sa.text("status = 'ACTIVE'"),
    )


def downgrade() -> None:
    op.drop_index("uq_trips_one_active_per_group", table_name="trips")
    op.drop_index("ix_trips_created_at", table_name="trips")
    op.drop_index("ix_trips_started_by", table_name="trips")
    op.drop_index("ix_trips_status", table_name="trips")
    op.drop_column("trips", "destination_name")
