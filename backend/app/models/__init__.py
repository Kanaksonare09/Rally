"""
Import every model here so (a) Base.metadata sees all tables for Alembic
autogenerate, and (b) SQLAlchemy can resolve the string-based relationship()
references between them regardless of import order.
"""

from app.core.database import Base
from app.models.auth_shadow import auth_users  # noqa: F401 — must load before Profile
from app.models.alert import Alert
from app.models.enums import (
    AlertSeverity,
    AlertStatus,
    AlertType,
    GroupStatus,
    MemberRole,
    MemberStatus,
    SOSStatus,
    TripStatus,
)
from app.models.group import Group
from app.models.group_member import GroupMember
from app.models.location_history import LocationHistory
from app.models.profile import Profile
from app.models.sos_event import SOSEvent
from app.models.trip import Trip

__all__ = [
    "Base",
    "Profile",
    "Group",
    "GroupMember",
    "Trip",
    "LocationHistory",
    "Alert",
    "SOSEvent",
    "GroupStatus",
    "MemberRole",
    "MemberStatus",
    "TripStatus",
    "AlertType",
    "AlertSeverity",
    "AlertStatus",
    "SOSStatus",
]
