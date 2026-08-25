import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.auth_shadow import auth_users  # noqa: F401 — registers the FK target below
from app.models.mixins import utc_now


class Profile(Base):
    """Application profile, one-to-one with a Supabase Auth user.

    `id` is NOT generated here — it must equal the corresponding
    auth.users.id, set at profile-creation time (a Supabase trigger commonly
    handles this; that trigger is not part of this phase).
    """

    __tablename__ = "profiles"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("auth.users.id", ondelete="CASCADE"),
        primary_key=True,
    )
    full_name: Mapped[Optional[str]] = mapped_column(String(150), nullable=True)
    avatar_url: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False
    )

    led_groups: Mapped[list["Group"]] = relationship(back_populates="leader")  # noqa: F821
    memberships: Mapped[list["GroupMember"]] = relationship(back_populates="user")  # noqa: F821
