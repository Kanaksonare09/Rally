import uuid
from typing import List

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.core.rate_limit import rate_limit_by_user
from app.dependencies.auth import get_current_user_id
from app.dependencies.group import require_group_member, require_group_leader
from app.models.group_member import GroupMember
from app.schemas.group import (
    GroupCreate,
    GroupJoin,
    GroupResponse,
    GroupMemberResponse,
    GroupListItem,
    TransferLeadershipRequest,
)
from app.services import group_service

router = APIRouter(tags=["Groups"])


@router.post("", response_model=GroupResponse, status_code=status.HTTP_201_CREATED)
def create_group_endpoint(
    group_data: GroupCreate,
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    """Create a new group. Authenticated user becomes the leader."""
    return group_service.create_group(db, uuid.UUID(user_id), group_data)


@router.post(
    "/join",
    response_model=GroupResponse,
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(rate_limit_by_user("join_group", lambda: settings.JOIN_GROUP_RATE_LIMIT_PER_MINUTE))],
)
def join_group_endpoint(
    join_data: GroupJoin,
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    """Join a group using a join code. Rate-limited per user
    (JOIN_GROUP_RATE_LIMIT_PER_MINUTE) — this is the one endpoint where a
    caller is effectively guessing a secret, so it gets its own stricter
    bound on top of the general API limit; see JOIN CODE PROTECTION in
    the README. A removed member trying to rejoin gets the same generic
    "cannot join this group" 403 as an inactive group, rather than a
    message that confirms they were specifically removed — see
    group_service.join_group."""
    return group_service.join_group(db, uuid.UUID(user_id), join_data.join_code)


@router.get("", response_model=List[GroupListItem])
def list_my_groups_endpoint(
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    """List all groups the authenticated user is currently active in."""
    return group_service.list_user_groups(db, uuid.UUID(user_id))


@router.get("/{group_id}", response_model=GroupResponse)
def get_group_endpoint(
    group_id: uuid.UUID,
    member: GroupMember = Depends(require_group_member),
    db: Session = Depends(get_db),
):
    """Get group details. Must be an active member."""
    return group_service.get_group(db, group_id)


@router.get("/{group_id}/members", response_model=List[GroupMemberResponse])
def get_group_members_endpoint(
    group_id: uuid.UUID,
    member: GroupMember = Depends(require_group_member),
    db: Session = Depends(get_db),
):
    """Get all active members of the group. Must be an active member."""
    return group_service.get_group_members_with_profiles(db, group_id)


@router.post("/{group_id}/leave", status_code=status.HTTP_204_NO_CONTENT)
def leave_group_endpoint(
    group_id: uuid.UUID,
    member: GroupMember = Depends(require_group_member),
    db: Session = Depends(get_db),
):
    """Leave the group. Leader must transfer leadership first."""
    group_service.leave_group(db, group_id, member.user_id)


@router.delete("/{group_id}/members/{target_user_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_member_endpoint(
    group_id: uuid.UUID,
    target_user_id: uuid.UUID,
    leader: GroupMember = Depends(require_group_leader),
    db: Session = Depends(get_db),
):
    """Remove a member from the group. Must be the leader."""
    group_service.remove_member(db, group_id, target_user_id, leader.user_id)


@router.post("/{group_id}/transfer-leadership", status_code=status.HTTP_204_NO_CONTENT)
def transfer_leadership_endpoint(
    group_id: uuid.UUID,
    request: TransferLeadershipRequest,
    leader: GroupMember = Depends(require_group_leader),
    db: Session = Depends(get_db),
):
    """Transfer leadership to another active member. Must be current leader."""
    group_service.transfer_leadership(db, group_id, leader.user_id, request.new_leader_id)
