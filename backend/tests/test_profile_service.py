"""
Unit tests for the get-or-create profile logic, using a fake Session
instead of a real Postgres connection — there's no live Supabase database
available in this environment (see backend README / final validation notes).
"""

import uuid

from app.models.profile import Profile
from app.services.profile_service import get_or_create_profile

USER_ID = "22222222-2222-2222-2222-222222222222"


class FakeSession:
    def __init__(self, existing: Profile | None = None):
        self._store: dict[uuid.UUID, Profile] = {}
        if existing is not None:
            self._store[existing.id] = existing
        self.added = []
        self.committed = False

    def get(self, model, pk):
        return self._store.get(pk)

    def add(self, obj):
        self.added.append(obj)
        self._store[obj.id] = obj

    def commit(self):
        self.committed = True

    def refresh(self, obj):
        pass

    def rollback(self):
        pass


def test_returns_existing_profile_without_creating():
    existing = Profile(id=uuid.UUID(USER_ID), full_name="Existing User")
    db = FakeSession(existing=existing)

    result = get_or_create_profile(db, user_id=USER_ID, full_name_hint="Should Not Be Used")

    assert result is existing
    assert result.full_name == "Existing User"
    assert db.added == []
    assert db.committed is False


def test_creates_profile_when_missing():
    db = FakeSession()

    result = get_or_create_profile(
        db, user_id=USER_ID, full_name_hint="New User", avatar_url_hint="https://x/a.png"
    )

    assert result.id == uuid.UUID(USER_ID)
    assert result.full_name == "New User"
    assert result.avatar_url == "https://x/a.png"
    assert db.committed is True
    assert len(db.added) == 1


def test_creates_profile_with_no_hints():
    db = FakeSession()

    result = get_or_create_profile(db, user_id=USER_ID)

    assert result.id == uuid.UUID(USER_ID)
    assert result.full_name is None
    assert result.avatar_url is None
