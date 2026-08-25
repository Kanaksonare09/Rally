"""
Get-or-create logic for application profiles. The profile id is always the
verified Supabase auth user id — callers never get to choose it.
"""

import logging
import uuid
from typing import Optional

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.profile import Profile

logger = logging.getLogger("rally.profile")


def get_profile(db: Session, user_id: str) -> Optional[Profile]:
    try:
        parsed_id = uuid.UUID(str(user_id))
    except (ValueError, AttributeError, TypeError):
        return None
    return db.get(Profile, parsed_id)


def get_or_create_profile(
    db: Session,
    user_id: str,
    full_name_hint: Optional[str] = None,
    avatar_url_hint: Optional[str] = None,
) -> Profile:
    """Returns the existing profile for user_id, or creates a minimal one.

    full_name_hint/avatar_url_hint are only ever used at creation time —
    they never overwrite an existing profile's fields on subsequent calls.
    """
    profile = get_profile(db, user_id)
    if profile is not None:
        return profile

    profile = Profile(id=uuid.UUID(str(user_id)), full_name=full_name_hint, avatar_url=avatar_url_hint)
    db.add(profile)
    try:
        db.commit()
    except IntegrityError:
        # Lost a race with a concurrent request that created the same
        # profile first — that's fine, just read back what's there.
        logger.info("Profile %s was created concurrently; reusing it.", user_id)
        db.rollback()
        profile = get_profile(db, user_id)
        if profile is None:
            raise
    else:
        db.refresh(profile)
    return profile
