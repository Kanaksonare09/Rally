import enum


class GroupStatus(str, enum.Enum):
    ACTIVE = "ACTIVE"
    COMPLETED = "COMPLETED"
    ARCHIVED = "ARCHIVED"


class MemberRole(str, enum.Enum):
    LEADER = "LEADER"
    MEMBER = "MEMBER"


class MemberStatus(str, enum.Enum):
    ACTIVE = "ACTIVE"
    LEFT = "LEFT"
    REMOVED = "REMOVED"


class TripStatus(str, enum.Enum):
    CREATED = "CREATED"
    ACTIVE = "ACTIVE"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"


class AlertType(str, enum.Enum):
    """The Phase 8 spec's exact "initially support" list — the Phase 1
    placeholder version of this enum (ROUTE_DEVIATION, CONNECTIVITY_LOSS,
    SOS) was never wired to any code, so it's replaced rather than
    extended. SOS is deliberately excluded: it's its own emergency system
    (app/sos/), never an alert."""

    FALLING_BEHIND = "FALLING_BEHIND"
    GROUP_SEPARATION = "GROUP_SEPARATION"
    ISOLATED_MEMBER = "ISOLATED_MEMBER"
    UNEXPECTED_STOP = "UNEXPECTED_STOP"
    SPEED_ANOMALY = "SPEED_ANOMALY"
    ROUTE_DEVIATION = "ROUTE_DEVIATION"  # Phase 9


class AlertSeverity(str, enum.Enum):
    INFO = "INFO"
    WARNING = "WARNING"
    CRITICAL = "CRITICAL"


class AlertStatus(str, enum.Enum):
    ACTIVE = "ACTIVE"
    ACKNOWLEDGED = "ACKNOWLEDGED"
    RESOLVED = "RESOLVED"


class SOSStatus(str, enum.Enum):
    ACTIVE = "ACTIVE"
    ACKNOWLEDGED = "ACKNOWLEDGED"
    RESOLVED = "RESOLVED"
    CANCELLED = "CANCELLED"


class IntelligenceEventType(str, enum.Enum):
    """Deliberately distinct from AlertType (Phase 1) — these are raw
    detections the Phase 8 alert engine will later decide whether/how to
    notify about, not user-facing alerts themselves. Includes movement
    *states* (MOVING/STOPPED) alongside anomaly detections, since both are
    "intelligence events" in this phase's model."""

    FALLING_BEHIND = "FALLING_BEHIND"
    GROUP_SEPARATION = "GROUP_SEPARATION"
    UNEXPECTED_STOP = "UNEXPECTED_STOP"
    SPEED_ANOMALY = "SPEED_ANOMALY"
    ISOLATED_MEMBER = "ISOLATED_MEMBER"
    MOVING_TOGETHER = "MOVING_TOGETHER"
    STOPPED = "STOPPED"
    MOVING = "MOVING"
    ROUTE_DEVIATION = "ROUTE_DEVIATION"  # Phase 9 — route intelligence


class IntelligenceSeverity(str, enum.Enum):
    INFO = "INFO"
    WARNING = "WARNING"
    CRITICAL = "CRITICAL"


class RouteStatus(str, enum.Enum):
    PLANNED = "PLANNED"
    ACTIVE = "ACTIVE"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"
