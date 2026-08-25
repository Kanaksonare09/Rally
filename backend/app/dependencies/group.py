import uuid
from typing import Optional

from fastapi import Depends, HTTPException, status, Path
from sqlalchemy.orm import Session
from sqlalchemy import select

from app.core.database import get_db
from app.core.errors import AppHTTPException
from app.dependencies.auth import get_current_user_id
from app.models.enums import MemberRole, MemberStatus
from app.models.group import Group
from app.models.group_member import GroupMember


def get_current_group_member(
    group_id: uuid.UUID = Path(...),
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
) -> GroupMember:
    """Retrieve the current user's membership for the specified group."""
    member = db.scalars(
        select(GroupMember).where(
            GroupMember.group_id == group_id, GroupMember.user_id == user_id
        )
    ).first()

    if not member:
        # Deliberately the same 404 whether the group doesn't exist or the
        # user just isn't a member — avoids leaking group existence.
        raise AppHTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            code="GROUP_NOT_FOUND",
            detail="Group not found or not a member.",
        )

    return member


def require_group_member(member: GroupMember = Depends(get_current_group_member)) -> GroupMember:
    """Ensure the current user is an active member of the group."""
    if member.status != MemberStatus.ACTIVE:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Not an active member of this group."
        )
    return member


def require_group_leader(member: GroupMember = Depends(require_group_member)) -> GroupMember:
    """Ensure the current user is the leader of the group."""
    if member.role != MemberRole.LEADER:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Only the group leader can perform this action."
        )
    return member
