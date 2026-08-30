"""
Event persistence lifecycle (create once, update while active, resolve,
allow a fresh event after resolution) against a fake DB session — no live
database, same FakeSession pattern as test_trip_service.py — plus
fakeredis for the active-event mirror key.
"""

import uuid
from datetime import datetime, timezone

import pytest
from sqlalchemy.exc import IntegrityError

import app.models  # noqa: F401 — registers every model before instantiation
from app.core.redis_keys import intel_active_event_key
from app.intelligence import events
from app.intelligence.detectors import DetectionResult
from app.models.enums import IntelligenceEventType, IntelligenceSeverity
from app.models.intelligence_event import IntelligenceEvent

TRIP_ID = uuid.uuid4()
GROUP_ID = uuid.uuid4()
USER_ID = uuid.uuid4()


class _ScalarResult:
    def __init__(self, value):
        self._value = value

    def first(self):
        return self._value


class FakeSession:
    def __init__(self, existing: IntelligenceEvent = None):
        self._existing = existing
        self.commits = 0
        self.rollbacks = 0
        self._raise_integrity_next = False

    def scalars(self, stmt):
        return _ScalarResult(self._existing)

    def add(self, obj):
        self._pending = obj

    def commit(self):
        if self._raise_integrity_next:
            self._raise_integrity_next = False
            raise IntegrityError("INSERT", {}, Exception("duplicate key"))
        self.commits += 1
        if getattr(self, "_pending", None) is not None:
            self._existing = self._pending  # so a subsequent lookup finds it

    def rollback(self):
        self.rollbacks += 1

    def refresh(self, obj):
        if obj.id is None:
            obj.id = uuid.uuid4()
        if obj.detected_at is None:
            obj.detected_at = datetime.now(timezone.utc)
        if obj.created_at is None:
            obj.created_at = datetime.now(timezone.utc)


def make_result(detected: bool, event_type=IntelligenceEventType.FALLING_BEHIND, user_id=str(USER_ID), metadata=None):
    return DetectionResult(
        event_type=event_type,
        severity=IntelligenceSeverity.WARNING,
        user_id=user_id,
        related_user_id=None,
        detected=detected,
        metadata=metadata or {"distance_meters": 700},
    )


# ---- create / dedup / resolve --------------------------------------------


async def test_event_created_once(fake_redis):
    db = FakeSession(existing=None)
    event, action = await events.apply_detection(db, fake_redis, TRIP_ID, GROUP_ID, make_result(True))

    assert action == "created"
    assert event.id is not None
    assert event.resolved_at is None
    assert db.commits == 1


async def test_repeated_evaluation_does_not_create_duplicates():
    """Once an event exists, subsequent detected=True ticks update it in
    place rather than inserting a new row."""
    import fakeredis

    redis = fakeredis.FakeAsyncRedis(decode_responses=True)
    db = FakeSession(existing=None)

    event1, action1 = await events.apply_detection(db, redis, TRIP_ID, GROUP_ID, make_result(True))
    assert action1 == "created"

    event2, action2 = await events.apply_detection(db, redis, TRIP_ID, GROUP_ID, make_result(True, metadata={"distance_meters": 800}))
    assert action2 == "updated"
    assert event2 is event1  # same row, not a new one
    assert event2.event_metadata == {"distance_meters": 800}


async def test_active_event_remains_active_while_condition_holds(fake_redis):
    db = FakeSession(existing=None)
    event, _ = await events.apply_detection(db, fake_redis, TRIP_ID, GROUP_ID, make_result(True))

    event2, action = await events.apply_detection(db, fake_redis, TRIP_ID, GROUP_ID, make_result(True))
    assert action == "updated"
    assert event2.resolved_at is None


async def test_event_resolves_correctly(fake_redis):
    db = FakeSession(existing=None)
    event, _ = await events.apply_detection(db, fake_redis, TRIP_ID, GROUP_ID, make_result(True))

    resolved_event, action = await events.apply_detection(db, fake_redis, TRIP_ID, GROUP_ID, make_result(False))

    assert action == "resolved"
    assert resolved_event is event
    assert resolved_event.resolved_at is not None


async def test_resolving_when_nothing_active_is_a_noop(fake_redis):
    db = FakeSession(existing=None)
    event, action = await events.apply_detection(db, fake_redis, TRIP_ID, GROUP_ID, make_result(False))
    assert action == "noop"
    assert event is None
    assert db.commits == 0


async def test_new_occurrence_after_resolution_creates_a_new_event():
    import fakeredis

    redis = fakeredis.FakeAsyncRedis(decode_responses=True)
    db = FakeSession(existing=None)

    first_event, action1 = await events.apply_detection(db, redis, TRIP_ID, GROUP_ID, make_result(True))
    assert action1 == "created"

    db._existing = first_event
    await events.apply_detection(db, redis, TRIP_ID, GROUP_ID, make_result(False))
    assert first_event.resolved_at is not None

    # The "existing" lookup should now find nothing (resolved rows aren't
    # active), so a fresh detection creates a brand new row.
    db._existing = None
    second_event, action2 = await events.apply_detection(db, redis, TRIP_ID, GROUP_ID, make_result(True))
    assert action2 == "created"
    assert second_event is not first_event


# ---- concurrency: the partial-unique-index race ---------------------------


async def test_concurrent_creation_is_handled_via_integrity_error(fake_redis):
    """Simulates two evaluators racing to create the same active event —
    the loser's INSERT hits the partial unique index and must be handled
    as a clean no-op, never crash or raise past this function."""
    db = FakeSession(existing=None)
    db._raise_integrity_next = True

    event, action = await events.apply_detection(db, fake_redis, TRIP_ID, GROUP_ID, make_result(True))

    assert action == "noop"
    assert event is None
    assert db.rollbacks == 1


# ---- Redis active-event mirror -------------------------------------------


async def test_active_event_mirror_set_in_redis_on_create(fake_redis):
    db = FakeSession(existing=None)
    event, _ = await events.apply_detection(db, fake_redis, TRIP_ID, GROUP_ID, make_result(True))

    key = intel_active_event_key(TRIP_ID, IntelligenceEventType.FALLING_BEHIND.value, str(USER_ID))
    assert await fake_redis.get(key) == str(event.id)


async def test_active_event_mirror_cleared_in_redis_on_resolve(fake_redis):
    db = FakeSession(existing=None)
    event, _ = await events.apply_detection(db, fake_redis, TRIP_ID, GROUP_ID, make_result(True))
    await events.apply_detection(db, fake_redis, TRIP_ID, GROUP_ID, make_result(False))

    key = intel_active_event_key(TRIP_ID, IntelligenceEventType.FALLING_BEHIND.value, str(USER_ID))
    assert await fake_redis.get(key) is None


# ---- group-level events (user_id=None) ------------------------------------


async def test_group_level_event_uses_null_user_id(fake_redis):
    db = FakeSession(existing=None)
    result = make_result(True, event_type=IntelligenceEventType.GROUP_SEPARATION, user_id=None)

    event, action = await events.apply_detection(db, fake_redis, TRIP_ID, GROUP_ID, result)

    assert action == "created"
    assert event.user_id is None


# ---- list_events / list_active_events ------------------------------------


def test_list_events_scopes_to_trip_and_orders_newest_first():
    class ListFakeSession:
        def __init__(self, rows):
            self._rows = rows

        def scalars(self, stmt):
            return _ScalarResult2(self._rows)

    class _ScalarResult2:
        def __init__(self, rows):
            self._rows = rows

        def all(self):
            return self._rows

    rows = ["row1", "row2"]
    db = ListFakeSession(rows)
    result = events.list_events(db, TRIP_ID, limit=50)
    assert result == rows
