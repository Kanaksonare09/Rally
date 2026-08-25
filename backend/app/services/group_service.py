import secrets
import string
import uuid
from typing import List, Optional

from fastapi import HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import select

from app.models.enums import GroupStatus, MemberRole, MemberStatus
from app.models.group import Group
from app.models.group_member import GroupMember
from app.models.profile import Profile
from app.schemas.group import GroupCreate

def generate_join_code() -> str:
    """Generate a unique, human-readable join code."""
    # Format: RALLY-XXXXX (alphanumeric uppercase, excluding confusing chars)
    alphabet = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
    suffix = "".join(secrets.choice(alphabet) for _ in range(5))
    return f"RALLY-{suffix}"


def create_group(db: Session, user_id: uuid.UUID, group_data: GroupCreate) -> Group:
    """Create a new group and make the creator the leader."""
    
    # 1. Generate unique join code
    join_code = generate_join_code()
    # Ensure uniqueness loop (simple implementation, practically collision is very low)
    while db.scalars(select(Group).where(Group.join_code == join_code)).first():
        join_code = generate_join_code()

    # 2. Create the Group
    destination = None
    if group_data.latitude is not None and group_data.longitude is not None:
        destination = f"POINT({group_data.longitude} {group_data.latitude})"

    group = Group(
        name=group_data.name,
        join_code=join_code,
        leader_id=user_id,
        destination_name=group_data.destination_name,
        destination=destination,
        status=GroupStatus.ACTIVE,
    )
    db.add(group)
    db.flush()  # To get group.id

    # 3. Create Leader Membership
    member = GroupMember(
        group_id=group.id,
        user_id=user_id,
        role=MemberRole.LEADER,
        status=MemberStatus.ACTIVE,
    )
    db.add(member)
    db.commit()
    db.refresh(group)
    
    return group


def join_group(db: Session, user_id: uuid.UUID, join_code: str) -> Group:
    """Join an active group using its join code."""
    join_code = join_code.strip().upper()
    
    group = db.scalars(select(Group).where(Group.join_code == join_code)).first()
    if not group:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Group not found or invalid join code.")
        
    if group.status != GroupStatus.ACTIVE:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Cannot join a non-active group.")

    # Check existing membership
    existing_member = db.scalars(
        select(GroupMember).where(GroupMember.group_id == group.id, GroupMember.user_id == user_id)
    ).first()

    if existing_member:
        if existing_member.status == MemberStatus.ACTIVE:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Already an active member of this group.")
        elif existing_member.status == MemberStatus.REMOVED:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You have been removed from this group.")
        elif existing_member.status == MemberStatus.LEFT:
            # Rejoin logic
            existing_member.status = MemberStatus.ACTIVE
            # Demote to member just in case they were a leader previously (though a leader cannot leave without transferring)
            existing_member.role = MemberRole.MEMBER
            db.commit()
            db.refresh(group)
            return group

    # Create new membership
    new_member = GroupMember(
        group_id=group.id,
        user_id=user_id,
        role=MemberRole.MEMBER,
        status=MemberStatus.ACTIVE,
    )
    db.add(new_member)
    db.commit()
    db.refresh(group)
    return group


def get_group(db: Session, group_id: uuid.UUID) -> Optional[Group]:
    return db.scalars(select(Group).where(Group.id == group_id)).first()


def get_group_members_with_profiles(db: Session, group_id: uuid.UUID):
    """Retrieve all active members with their profiles."""
    stmt = (
        select(GroupMember, Profile)
        .join(Profile, GroupMember.user_id == Profile.id)
        .where(GroupMember.group_id == group_id, GroupMember.status == MemberStatus.ACTIVE)
    )
    results = db.execute(stmt).all()
    
    members_data = []
    for member, profile in results:
        members_data.append({
            "user_id": member.user_id,
            "name": profile.full_name_hint,
            "avatar_url": profile.avatar_url_hint,
            "role": member.role,
            "status": member.status,
            "joined_at": member.joined_at,
        })
    return members_data


def list_user_groups(db: Session, user_id: uuid.UUID):
    """List all groups where the user is an active member."""
    stmt = (
        select(Group, GroupMember)
        .join(GroupMember, Group.id == GroupMember.group_id)
        .where(GroupMember.user_id == user_id, GroupMember.status == MemberStatus.ACTIVE)
    )
    results = db.execute(stmt).all()
    
    groups_data = []
    for group, member in results:
        groups_data.append({
            "id": group.id,
            "name": group.name,
            "role": member.role,
            "status": group.status,
        })
    return groups_data


def leave_group(db: Session, group_id: uuid.UUID, user_id: uuid.UUID):
    """Allow a user to leave a group."""
    member = db.scalars(
        select(GroupMember).where(GroupMember.group_id == group_id, GroupMember.user_id == user_id)
    ).first()
    
    if not member or member.status != MemberStatus.ACTIVE:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Active membership not found.")
        
    if member.role == MemberRole.LEADER:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Leader cannot leave without transferring leadership first.")
        
    member.status = MemberStatus.LEFT
    db.commit()


def remove_member(db: Session, group_id: uuid.UUID, target_user_id: uuid.UUID, leader_id: uuid.UUID):
    """Remove a member from a group."""
    if target_user_id == leader_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Leader cannot remove themselves.")
        
    target_member = db.scalars(
        select(GroupMember).where(GroupMember.group_id == group_id, GroupMember.user_id == target_user_id)
    ).first()
    
    if not target_member or target_member.status != MemberStatus.ACTIVE:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Target active membership not found.")
        
    target_member.status = MemberStatus.REMOVED
    db.commit()


def transfer_leadership(db: Session, group_id: uuid.UUID, current_leader_id: uuid.UUID, new_leader_id: uuid.UUID):
    """Transfer group leadership to another active member."""
    if current_leader_id == new_leader_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Already the leader.")

    group = get_group(db, group_id)
    if not group:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Group not found.")
        
    current_leader_membership = db.scalars(
        select(GroupMember).where(GroupMember.group_id == group_id, GroupMember.user_id == current_leader_id)
    ).first()
    
    new_leader_membership = db.scalars(
        select(GroupMember).where(GroupMember.group_id == group_id, GroupMember.user_id == new_leader_id)
    ).first()
    
    if not new_leader_membership or new_leader_membership.status != MemberStatus.ACTIVE:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="New leader must be an active member of the group.")
        
    # Perform transfer in one transaction
    current_leader_membership.role = MemberRole.MEMBER
    new_leader_membership.role = MemberRole.LEADER
    group.leader_id = new_leader_id
    
    db.commit()
