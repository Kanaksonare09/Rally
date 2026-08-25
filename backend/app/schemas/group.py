import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import GroupStatus, MemberRole, MemberStatus


class GroupCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=150)
    destination_name: Optional[str] = Field(None, max_length=255)
    # Optional coordinates for the future if needed
    latitude: Optional[float] = Field(None, ge=-90, le=90)
    longitude: Optional[float] = Field(None, ge=-180, le=180)


class GroupJoin(BaseModel):
    join_code: str = Field(..., min_length=3, max_length=20)


class GroupResponse(BaseModel):
    id: uuid.UUID
    name: str
    join_code: str
    leader_id: Optional[uuid.UUID]
    destination_name: Optional[str]
    status: GroupStatus
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class GroupMemberResponse(BaseModel):
    user_id: uuid.UUID
    name: Optional[str] = None
    avatar_url: Optional[str] = None
    role: MemberRole
    status: MemberStatus
    joined_at: datetime

    model_config = ConfigDict(from_attributes=True)


class GroupListItem(BaseModel):
    id: uuid.UUID
    name: str
    role: MemberRole
    status: GroupStatus

    model_config = ConfigDict(from_attributes=True)


class TransferLeadershipRequest(BaseModel):
    new_leader_id: uuid.UUID
