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
    IntelligenceEventType,
    IntelligenceSeverity,
    MemberRole,
    MemberStatus,
    RouteStatus,
    SOSStatus,
    TripStatus,
)
from app.models.group import Group
from app.models.group_member import GroupMember
from app.models.intelligence_event import IntelligenceEvent
from app.models.location_history import LocationHistory
from app.models.notification import Notification
from app.models.profile import Profile
from app.models.route import Route
from app.models.sos_event import SOSEvent
from app.models.trip import Trip
from app.models.trip_analytics_snapshot import TripAnalyticsSnapshot

__all__ = [
    "Base",
    "Profile",
    "Group",
    "GroupMember",
    "Trip",
    "LocationHistory",
    "Alert",
    "SOSEvent",
    "IntelligenceEvent",
    "Route",
    "TripAnalyticsSnapshot",
    "Notification",
    "GroupStatus",
    "MemberRole",
    "MemberStatus",
    "TripStatus",
    "AlertType",
    "AlertSeverity",
    "AlertStatus",
    "SOSStatus",
    "IntelligenceEventType",
    "IntelligenceSeverity",
    "RouteStatus",
]
