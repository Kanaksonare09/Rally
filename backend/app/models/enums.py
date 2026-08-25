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
    FALLING_BEHIND = "FALLING_BEHIND"
    GROUP_SEPARATION = "GROUP_SEPARATION"
    ROUTE_DEVIATION = "ROUTE_DEVIATION"
    UNEXPECTED_STOP = "UNEXPECTED_STOP"
    CONNECTIVITY_LOSS = "CONNECTIVITY_LOSS"
    SPEED_ANOMALY = "SPEED_ANOMALY"
    SOS = "SOS"


class AlertSeverity(str, enum.Enum):
    INFO = "INFO"
    WARNING = "WARNING"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class AlertStatus(str, enum.Enum):
    ACTIVE = "ACTIVE"
    RESOLVED = "RESOLVED"


class SOSStatus(str, enum.Enum):
    ACTIVE = "ACTIVE"
    RESOLVED = "RESOLVED"
    CANCELLED = "CANCELLED"
