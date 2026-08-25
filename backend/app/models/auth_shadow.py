"""
A minimal, unmanaged reference to Supabase's own auth.users table.

We don't own this table — Supabase does — so it's declared as a plain Core
Table (not a mapped class, no relationships) purely so SQLAlchemy has a real
target to resolve `ForeignKey("auth.users.id")` against when it configures
the ORM mappers. Nothing here is created, altered, or dropped by our own
Alembic migrations.
"""

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

from app.core.database import Base

auth_users = sa.Table(
    "users",
    Base.metadata,
    sa.Column("id", UUID(as_uuid=True), primary_key=True),
    schema="auth",
)
