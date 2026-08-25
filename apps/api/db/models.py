import uuid
from datetime import datetime, timezone
from sqlalchemy import (
    Column, String, Text, Integer, Float, Boolean, DateTime, ForeignKey, Enum as SQLEnum, JSON
)
from sqlalchemy.orm import relationship
import enum
from apps.api.core.database import Base

def generate_uuid():
    return str(uuid.uuid4())

def utc_now():
    return datetime.now(timezone.utc)

class UserRole(str, enum.Enum):
    USER = "USER"
    ADMIN = "ADMIN"

class MemberRole(str, enum.Enum):
    OWNER = "OWNER"
    ADMIN = "ADMIN"
    MEMBER = "MEMBER"

class TripStatus(str, enum.Enum):
    PLANNED = "PLANNED"
    ACTIVE = "ACTIVE"
    PAUSED = "PAUSED"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"

class RiskLevel(str, enum.Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"

class AlertType(str, enum.Enum):
    DRIFTING = "DRIFTING"
    SEPARATION = "SEPARATION"
    ROUTE_DEVIATION = "ROUTE_DEVIATION"
    UNEXPECTED_STOP = "UNEXPECTED_STOP"
    CONNECTIVITY_LOSS = "CONNECTIVITY_LOSS"
    SOS = "SOS"

class AlertSeverity(str, enum.Enum):
    INFO = "INFO"
    WARNING = "WARNING"
    DANGER = "DANGER"
    CRITICAL = "CRITICAL"

class UserModel(Base):
    __tablename__ = "users"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    email = Column(String(255), unique=True, nullable=False, index=True)
    hashed_password = Column(String(255), nullable=False)
    full_name = Column(String(100), nullable=False)
    phone = Column(String(30), nullable=True)
    avatar_url = Column(Text, nullable=True)
    role = Column(SQLEnum(UserRole), default=UserRole.USER)
    created_at = Column(DateTime(timezone=True), default=utc_now)
    updated_at = Column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)

    profile = relationship("ProfileModel", back_populates="user", uselist=False, cascade="all, delete-orphan")
    group_memberships = relationship("GroupMemberModel", back_populates="user", cascade="all, delete-orphan")

class ProfileModel(Base):
    __tablename__ = "profiles"

    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    bio = Column(Text, nullable=True)
    emergency_contact_name = Column(String(100), nullable=True)
    emergency_contact_phone = Column(String(30), nullable=True)
    default_activity = Column(String(50), default="road_trip")
    location_sharing_enabled = Column(Boolean, default=True)
    updated_at = Column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)

    user = relationship("UserModel", back_populates="profile")

class GroupModel(Base):
    __tablename__ = "groups"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    name = Column(String(100), nullable=False)
    description = Column(Text, nullable=True)
    code = Column(String(12), unique=True, nullable=False, index=True)
    max_members = Column(Integer, default=20)
    safe_distance_threshold_m = Column(Float, default=150.0)
    drifting_threshold_m = Column(Float, default=250.0)
    critical_separation_m = Column(Float, default=350.0)
    created_by = Column(String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime(timezone=True), default=utc_now)
    updated_at = Column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)

    members = relationship("GroupMemberModel", back_populates="group", cascade="all, delete-orphan")
    trips = relationship("TripModel", back_populates="group", cascade="all, delete-orphan")

class GroupMemberModel(Base):
    __tablename__ = "group_members"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    group_id = Column(String(36), ForeignKey("groups.id", ondelete="CASCADE"), nullable=False)
    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    role = Column(SQLEnum(MemberRole), default=MemberRole.MEMBER)
    joined_at = Column(DateTime(timezone=True), default=utc_now)
    is_active = Column(Boolean, default=True)

    group = relationship("GroupModel", back_populates="members")
    user = relationship("UserModel", back_populates="group_memberships")

class TripModel(Base):
    __tablename__ = "trips"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    group_id = Column(String(36), ForeignKey("groups.id", ondelete="CASCADE"), nullable=False)
    name = Column(String(100), nullable=False)
    status = Column(SQLEnum(TripStatus), default=TripStatus.PLANNED)
    created_by = Column(String(36), ForeignKey("users.id"), nullable=False)
    started_at = Column(DateTime(timezone=True), nullable=True)
    ended_at = Column(DateTime(timezone=True), nullable=True)
    planned_route_waypoints = Column(JSON, nullable=True)
    created_at = Column(DateTime(timezone=True), default=utc_now)
    updated_at = Column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)

    group = relationship("GroupModel", back_populates="trips")

class LocationPointModel(Base):
    __tablename__ = "location_points"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    trip_id = Column(String(36), ForeignKey("trips.id", ondelete="CASCADE"), nullable=False, index=True)
    group_id = Column(String(36), ForeignKey("groups.id", ondelete="CASCADE"), nullable=False, index=True)
    latitude = Column(Float, nullable=False)
    longitude = Column(Float, nullable=False)
    accuracy = Column(Float, nullable=True)
    speed = Column(Float, nullable=True)
    heading = Column(Float, nullable=True)
    altitude = Column(Float, nullable=True)
    battery_level = Column(Float, nullable=True)
    connectivity_state = Column(String(20), default="ONLINE")
    device_timestamp = Column(DateTime(timezone=True), nullable=False, index=True)
    server_timestamp = Column(DateTime(timezone=True), default=utc_now)
    is_offline_synced = Column(Boolean, default=False)

class AlertModel(Base):
    __tablename__ = "alerts"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    trip_id = Column(String(36), ForeignKey("trips.id", ondelete="CASCADE"), nullable=False, index=True)
    group_id = Column(String(36), ForeignKey("groups.id", ondelete="CASCADE"), nullable=False)
    target_user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    alert_type = Column(SQLEnum(AlertType), nullable=False)
    severity = Column(SQLEnum(AlertSeverity), nullable=False)
    title = Column(String(150), nullable=False)
    message = Column(Text, nullable=False)
    metadata_json = Column(JSON, default={})
    is_resolved = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), default=utc_now)

class RecommendationModel(Base):
    __tablename__ = "recommendations"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    trip_id = Column(String(36), ForeignKey("trips.id", ondelete="CASCADE"), nullable=False, index=True)
    group_id = Column(String(36), ForeignKey("groups.id", ondelete="CASCADE"), nullable=False)
    trigger_alert_id = Column(String(36), ForeignKey("alerts.id", ondelete="SET NULL"), nullable=True)
    action_text = Column(String(255), nullable=False)
    reason = Column(Text, nullable=False)
    priority = Column(Integer, default=1)
    is_acknowledged = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), default=utc_now)

class SOSAlertModel(Base):
    __tablename__ = "sos_alerts"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    trip_id = Column(String(36), ForeignKey("trips.id", ondelete="CASCADE"), nullable=False, index=True)
    group_id = Column(String(36), ForeignKey("groups.id", ondelete="CASCADE"), nullable=False)
    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    latitude = Column(Float, nullable=False)
    longitude = Column(Float, nullable=False)
    status = Column(String(20), default="ACTIVE")
    created_at = Column(DateTime(timezone=True), default=utc_now)
