"""
SOS service tests: PostgreSQL persistence, the Redis active-state mirror
(and specifically that it carries NO TTL — the SOS safety rule), and the
lifecycle transitions (acknowledge/resolve/cancel), including that only
the original creator may cancel. No live database — FakeSession, same
pattern as the rest of this test suite; fakeredis for the Redis half.
"""

import uuid
from datetime import datetime, timezone
from types import SimpleNamespace

import fakeredis
import pytest

from app.core.errors import AppHTTPException
from app.core.redis_keys import sos_active_key, trip_active_sos_key
from app.models.enums import SOSStatus
from app.schemas.sos import SOSCreate
from app.sos import service as sos_service

TRIP_ID = uuid.uuid4()
GROUP_ID = uuid.uuid4()
USER_ID = uuid.uuid4()
OTHER_USER_ID = uuid.uuid4()


class _ScalarResult:
    def __init__(self, value):
        self._value = value

    def first(self):
        return self._value


class FakeSession:
    def __init__(self, existing_active_sos=None):
        self.added = []
        self.commits = 0
        # trigger_sos's idempotency check (app/sos/service.py) queries for
        # an existing ACTIVE/ACKNOWLEDGED SOS before creating a new one —
        # None by default (every test here starts from "no prior SOS"),
        # overridable for the dedup-specific tests below.
        self._existing_active_sos = existing_active_sos

    def add(self, obj):
        self.added.append(obj)

    def scalars(self, stmt):
        return _ScalarResult(self._existing_active_sos)

    def commit(self):
        self.commits += 1

    def refresh(self, obj):
        if obj.id is None:
            obj.id = uuid.uuid4()
        if obj.triggered_at is None:
            obj.triggered_at = datetime.now(timezone.utc)


def make_data(**overrides):
    kwargs = dict(latitude=22.7196, longitude=75.8577, accuracy=8.5, message="Need help")
    kwargs.update(overrides)
    return SOSCreate(**kwargs)


# ---- trigger: persistence + Redis mirror -----------------------------


async def test_sos_is_stored_in_postgresql(fake_redis):
    db = FakeSession()
    sos = await sos_service.trigger_sos(db, fake_redis, TRIP_ID, GROUP_ID, USER_ID, make_data())

    assert db.commits == 1
    assert sos.status == SOSStatus.ACTIVE
    assert sos.user_id == USER_ID
    assert sos.trip_id == TRIP_ID
    assert sos.latitude == 22.7196
    assert sos.message == "Need help"


async def test_sos_active_state_stored_in_redis(fake_redis):
    db = FakeSession()
    sos = await sos_service.trigger_sos(db, fake_redis, TRIP_ID, GROUP_ID, USER_ID, make_data())

    raw = await fake_redis.get(sos_active_key(TRIP_ID, sos.id))
    assert raw is not None

    members = await fake_redis.smembers(trip_active_sos_key(TRIP_ID))
    assert str(sos.id) in members


async def test_sos_active_state_has_no_ttl(fake_redis):
    """The SOS safety rule: nothing about SOS lifecycle is governed by
    expiry. A TTL here would let it silently vanish from "active" without
    ever being resolved."""
    db = FakeSession()
    sos = await sos_service.trigger_sos(db, fake_redis, TRIP_ID, GROUP_ID, USER_ID, make_data())

    ttl = await fake_redis.ttl(sos_active_key(TRIP_ID, sos.id))
    assert ttl == -1  # -1 means "exists, no expiry" in Redis


async def test_sos_still_persists_even_if_redis_is_unavailable():
    """PostgreSQL must remain the record of truth — a missing/broken Redis
    must never mean an SOS is silently lost."""
    db = FakeSession()
    sos = await sos_service.trigger_sos(db, None, TRIP_ID, GROUP_ID, USER_ID, make_data())

    assert db.commits == 1
    assert sos.status == SOSStatus.ACTIVE


# ---- idempotency (Phase 11, Part 7) ---------------------------------------


async def test_duplicate_trigger_returns_existing_active_sos_not_a_new_one(fake_redis):
    """A retried/duplicate request while an SOS is already ACTIVE for this
    user+trip must return that same SOS, never create a second row."""
    existing = SimpleNamespace(id=uuid.uuid4(), user_id=USER_ID, trip_id=TRIP_ID, status=SOSStatus.ACTIVE)
    db = FakeSession(existing_active_sos=existing)

    result = await sos_service.trigger_sos(db, fake_redis, TRIP_ID, GROUP_ID, USER_ID, make_data())

    assert result is existing
    assert db.commits == 0  # nothing new written
    assert db.added == []


async def test_duplicate_trigger_also_deduped_while_acknowledged(fake_redis):
    """An ACKNOWLEDGED (not just ACTIVE) SOS still blocks a duplicate —
    "someone's responding to it" is not "it's over"."""
    existing = SimpleNamespace(id=uuid.uuid4(), user_id=USER_ID, trip_id=TRIP_ID, status=SOSStatus.ACKNOWLEDGED)
    db = FakeSession(existing_active_sos=existing)

    result = await sos_service.trigger_sos(db, fake_redis, TRIP_ID, GROUP_ID, USER_ID, make_data())

    assert result is existing
    assert db.commits == 0


async def test_new_trigger_allowed_once_previous_sos_is_resolved(fake_redis):
    """No dedup block once the prior emergency is over — a genuinely new
    SOS must always be creatable."""
    db = FakeSession(existing_active_sos=None)  # RESOLVED/CANCELLED rows never come back from the dedup query

    result = await sos_service.trigger_sos(db, fake_redis, TRIP_ID, GROUP_ID, USER_ID, make_data())

    assert db.commits == 1
    assert result.status == SOSStatus.ACTIVE


# ---- acknowledge / resolve / cancel -----------------------------------


async def test_sos_can_be_acknowledged(fake_redis):
    db = FakeSession()
    sos = await sos_service.trigger_sos(db, fake_redis, TRIP_ID, GROUP_ID, USER_ID, make_data())

    updated = await sos_service.acknowledge_sos(db, fake_redis, sos)

    assert updated.status == SOSStatus.ACKNOWLEDGED
    assert updated.acknowledged_at is not None


async def test_sos_can_be_resolved(fake_redis):
    db = FakeSession()
    sos = await sos_service.trigger_sos(db, fake_redis, TRIP_ID, GROUP_ID, USER_ID, make_data())

    updated = await sos_service.resolve_sos(db, fake_redis, sos)

    assert updated.status == SOSStatus.RESOLVED
    assert updated.resolved_at is not None


async def test_resolved_sos_remains_in_postgresql_history(fake_redis):
    """Resolving clears the Redis mirror but never deletes the row."""
    db = FakeSession()
    sos = await sos_service.trigger_sos(db, fake_redis, TRIP_ID, GROUP_ID, USER_ID, make_data())
    await sos_service.resolve_sos(db, fake_redis, sos)

    assert sos in db.added  # never removed from "the database"
    assert sos.status == SOSStatus.RESOLVED


async def test_resolving_clears_active_redis_state(fake_redis):
    db = FakeSession()
    sos = await sos_service.trigger_sos(db, fake_redis, TRIP_ID, GROUP_ID, USER_ID, make_data())

    await sos_service.resolve_sos(db, fake_redis, sos)

    assert await fake_redis.get(sos_active_key(TRIP_ID, sos.id)) is None
    members = await fake_redis.smembers(trip_active_sos_key(TRIP_ID))
    assert str(sos.id) not in members


async def test_creator_can_cancel_sos(fake_redis):
    db = FakeSession()
    sos = await sos_service.trigger_sos(db, fake_redis, TRIP_ID, GROUP_ID, USER_ID, make_data())

    updated = await sos_service.cancel_sos(db, fake_redis, sos, requesting_user_id=USER_ID)

    assert updated.status == SOSStatus.CANCELLED


async def test_another_user_cannot_cancel_sos(fake_redis):
    db = FakeSession()
    sos = await sos_service.trigger_sos(db, fake_redis, TRIP_ID, GROUP_ID, USER_ID, make_data())

    with pytest.raises(AppHTTPException) as exc_info:
        await sos_service.cancel_sos(db, fake_redis, sos, requesting_user_id=OTHER_USER_ID)

    assert exc_info.value.status_code == 403
    assert sos.status == SOSStatus.ACTIVE  # unchanged


async def test_cannot_acknowledge_already_resolved_sos(fake_redis):
    db = FakeSession()
    sos = await sos_service.trigger_sos(db, fake_redis, TRIP_ID, GROUP_ID, USER_ID, make_data())
    await sos_service.resolve_sos(db, fake_redis, sos)

    with pytest.raises(AppHTTPException) as exc_info:
        await sos_service.acknowledge_sos(db, fake_redis, sos)
    assert exc_info.value.status_code == 409


async def test_concurrent_double_resolution_is_safe(fake_redis):
    """The second resolve call on an already-resolved SOS must fail
    cleanly, not silently succeed or corrupt state."""
    db = FakeSession()
    sos = await sos_service.trigger_sos(db, fake_redis, TRIP_ID, GROUP_ID, USER_ID, make_data())

    await sos_service.resolve_sos(db, fake_redis, sos)
    with pytest.raises(AppHTTPException) as exc_info:
        await sos_service.resolve_sos(db, fake_redis, sos)
    assert exc_info.value.status_code == 409


# ---- validation (reused Pydantic rules, same as REST location endpoint) ---


def test_invalid_latitude_rejected():
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        SOSCreate(latitude=91, longitude=0)


def test_invalid_longitude_rejected():
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        SOSCreate(latitude=0, longitude=181)


def test_invalid_accuracy_rejected():
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        SOSCreate(latitude=0, longitude=0, accuracy=-1)


def test_sos_create_has_no_trusted_identity_fields():
    forbidden = {"id", "trip_id", "group_id", "user_id", "status", "created_at"}
    assert forbidden.isdisjoint(SOSCreate.model_fields.keys())
