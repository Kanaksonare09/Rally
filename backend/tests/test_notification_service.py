"""
app/notifications/service.py: creation + dedup, list/count/mark-read, and
the "same 404 whether missing or someone else's" ownership check — same
FakeSession pattern used throughout this backend's test suite.
"""

import uuid
from datetime import datetime, timezone

import pytest
from sqlalchemy.exc import IntegrityError

import app.models  # noqa: F401 — registers every model before instantiation
from app.core.errors import AppHTTPException
from app.models.notification import Notification
from app.notifications import service as notification_service

USER_ID = uuid.uuid4()
OTHER_USER_ID = uuid.uuid4()
TRIP_ID = uuid.uuid4()


class _ScalarResult:
    def __init__(self, values):
        self._values = values if isinstance(values, list) else [values]

    def first(self):
        return self._values[0] if self._values else None

    def all(self):
        return self._values


class FakeSession:
    def __init__(self, existing=None, raise_integrity_next=False):
        self._existing = existing or []
        self.commits = 0
        self._raise_integrity_next = raise_integrity_next
        self.added = []

    def add(self, obj):
        self.added.append(obj)

    def scalars(self, stmt):
        return _ScalarResult(self._existing)

    def scalar(self, stmt):
        return len(self._existing)

    def commit(self):
        if self._raise_integrity_next:
            self._raise_integrity_next = False
            raise IntegrityError("INSERT", {}, Exception("duplicate key"))
        self.commits += 1
        if self.added:
            self._existing = self.added

    def rollback(self):
        pass

    def refresh(self, obj):
        if obj.id is None:
            obj.id = uuid.uuid4()
        if obj.created_at is None:
            obj.created_at = datetime.now(timezone.utc)

    def get(self, model, pk):
        for obj in self._existing:
            if obj.id == pk:
                return obj
        return None


def make_notification(**overrides) -> Notification:
    n = Notification(
        id=uuid.uuid4(), user_id=USER_ID, trip_id=TRIP_ID, type="TRIP_STARTED",
        title="Trip started", message="Your trip has started.", severity="INFO",
        dedup_key=None, notification_metadata={}, read_at=None, created_at=datetime.now(timezone.utc),
    )
    for k, v in overrides.items():
        setattr(n, k, v)
    return n


# ---- creation + dedup -------------------------------------------------


def test_notify_creates_a_notification():
    db = FakeSession()
    result = notification_service.notify(
        db, user_id=USER_ID, type="TRIP_STARTED", title="Trip started", message="Go!", trip_id=TRIP_ID
    )
    assert result is not None
    assert db.commits == 1
    assert result.user_id == USER_ID


def test_notify_with_dedup_key_deduplicated_via_integrity_error():
    """Simulates the database's partial unique index rejecting a second
    row for the same (user_id, dedup_key) — the actual guarantee, not
    just an app-level check."""
    db = FakeSession(raise_integrity_next=True)
    result = notification_service.notify(
        db, user_id=USER_ID, type="FALLING_BEHIND", title="x", message="y", dedup_key="alert:123"
    )
    assert result is None


def test_notify_many_fans_out_to_every_user():
    db = FakeSession()
    results = notification_service.notify_many(
        db, user_ids=[USER_ID, OTHER_USER_ID], type="TRIP_STARTED", title="x", message="y"
    )
    assert len(results) == 2


def test_notify_many_uses_per_user_dedup_key():
    """A shared dedup_key across every recipient would make every user
    after the first silently deduplicated — dedup_key_fn must vary."""
    db = FakeSession()
    seen_keys = []

    def dedup_key_fn(user_id):
        key = f"trip_started:{TRIP_ID}:{user_id}"
        seen_keys.append(key)
        return key

    notification_service.notify_many(
        db, user_ids=[USER_ID, OTHER_USER_ID], type="TRIP_STARTED", title="x", message="y", dedup_key_fn=dedup_key_fn
    )
    assert len(set(seen_keys)) == 2  # genuinely different per user


def test_notify_safely_swallows_exceptions():
    class ExplodingSession:
        def add(self, obj):
            raise RuntimeError("db is down")

    result = notification_service.notify_safely(ExplodingSession(), user_id=USER_ID, type="x", title="x", message="x")
    assert result is None  # never raises


# ---- reads --------------------------------------------------------------


def test_list_notifications_scoped_to_user():
    db = FakeSession(existing=[make_notification()])
    items = notification_service.list_notifications(db, USER_ID)
    assert len(items) == 1


def test_unread_count():
    db = FakeSession(existing=[make_notification(), make_notification()])
    assert notification_service.get_unread_count(db, USER_ID) == 2


# ---- ownership / read state ----------------------------------------------


def test_get_notification_for_owner_succeeds():
    notification = make_notification()
    db = FakeSession(existing=[notification])
    result = notification_service.get_notification_for_user(db, notification.id, USER_ID)
    assert result is notification


def test_get_notification_for_non_owner_is_404():
    notification = make_notification(user_id=OTHER_USER_ID)
    db = FakeSession(existing=[notification])
    with pytest.raises(AppHTTPException) as exc_info:
        notification_service.get_notification_for_user(db, notification.id, USER_ID)
    assert exc_info.value.status_code == 404
    assert exc_info.value.code == "NOTIFICATION_NOT_FOUND"


def test_get_missing_notification_is_the_same_404():
    db = FakeSession(existing=[])
    with pytest.raises(AppHTTPException) as exc_info:
        notification_service.get_notification_for_user(db, uuid.uuid4(), USER_ID)
    assert exc_info.value.code == "NOTIFICATION_NOT_FOUND"


def test_mark_read_sets_timestamp():
    notification = make_notification(read_at=None)
    db = FakeSession()
    updated = notification_service.mark_read(db, notification)
    assert updated.read_at is not None
    assert db.commits == 1


def test_mark_read_is_idempotent():
    already_read = datetime.now(timezone.utc)
    notification = make_notification(read_at=already_read)
    db = FakeSession()
    updated = notification_service.mark_read(db, notification)
    assert updated.read_at == already_read
    assert db.commits == 0  # no-op, never re-touched


def test_mark_all_read_returns_count_of_unread_only():
    unread = [make_notification(), make_notification()]
    db = FakeSession(existing=unread)
    marked = notification_service.mark_all_read(db, USER_ID)
    assert marked == 2
    assert all(n.read_at is not None for n in unread)
