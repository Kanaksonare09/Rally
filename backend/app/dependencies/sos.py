"""
Authorization for the top-level /sos/{sos_id} routes — mirrors
app/dependencies/alert.py exactly (same existence-hiding rationale: an SOS
that doesn't exist and one belonging to a group the caller isn't an
active member of both return the same 404)."""

import uuid
from typing import Tuple

from fastapi import Depends, Path, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.errors import AppHTTPException
from app.dependencies.auth import get_current_user_id
from app.models.enums import MemberStatus
from app.models.group_member import GroupMember
from app.models.sos_event import SOSEvent


def get_sos_or_404(sos_id: uuid.UUID = Path(...), db: Session = Depends(get_db)) -> SOSEvent:
    sos = db.get(SOSEvent, sos_id)
    if not sos:
        raise AppHTTPException(status_code=status.HTTP_404_NOT_FOUND, code="SOS_NOT_FOUND", detail="SOS event not found.")
    return sos


def get_sos_membership(
    user_id: str = Depends(get_current_user_id),
    sos: SOSEvent = Depends(get_sos_or_404),
    db: Session = Depends(get_db),
) -> Tuple[SOSEvent, GroupMember]:
    member = db.scalars(
        select(GroupMember).where(GroupMember.group_id == sos.group_id, GroupMember.user_id == user_id)
    ).first()
    if not member or member.status != MemberStatus.ACTIVE:
        raise AppHTTPException(status_code=status.HTTP_404_NOT_FOUND, code="SOS_NOT_FOUND", detail="SOS event not found.")
    return sos, member


def require_sos_member(pair: Tuple[SOSEvent, GroupMember] = Depends(get_sos_membership)) -> SOSEvent:
    sos, _member = pair
    return sos
