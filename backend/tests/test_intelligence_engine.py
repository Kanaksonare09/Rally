"""
Engine-level tests: compute_current_state() (the read path shared by the
worker and GET /trips/{id}/intelligence) and evaluate_and_persist_trip()
(the worker's per-trip tick — locking, persistence, WebSocket publish).
No live database — a fake session backs the one membership query;
fakeredis backs everything else. See tests/conftest.py.
"""

import json
import uuid
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import fakeredis
import pytest

from app.core.redis_keys import intel_condition_key
from app.intelligence import engine
from app.intelligence.thresholds import current_thresholds
from app.models.enums import IntelligenceEventType, MemberRole
from app.services import live_state_service, presence_service
from app.websocket.manager import ConnectionManager

TRIP_ID = uuid.uuid4()
GROUP_ID = uuid.uuid4()
USER_A = uuid.uuid4()
USER_B = uuid.uuid4()


class _ExecuteResult:
    def __init__(self, rows):
        self._rows = rows

    def all(self):
        return self._rows


class _ScalarResult:
    def first(self):
        return None  # every test here starts from "no existing active event"


class FakeSession:
    """Backs both the one membership query (_load_active_members_sync,
    via .execute().all()) and event persistence (events.py, via
    .scalars()/.add()/.commit()/.refresh()) — evaluate_and_persist_trip()
    needs both in the same session."""

    def __init__(self, member_rows):
        self._member_rows = member_rows

    def execute(self, stmt):
        return _ExecuteResult(self._member_rows)

    def scalars(self, stmt):
        return _ScalarResult()

    def add(self, obj):
        pass

    def commit(self):
        pass

    def refresh(self, obj):
        """Simulates the server-side defaults a real INSERT would apply.
        Generic over row type (IntelligenceEvent, or an Alert created by
        the Phase 8 hook this evaluation now also exercises) — only sets
        an attribute if the model actually has it."""
        if getattr(obj, "id", "unset") is None:
            obj.id = uuid.uuid4()
        for attr in ("detected_at", "created_at"):
            if getattr(obj, attr, "unset") is None:
                setattr(obj, attr, datetime.now(timezone.utc))

    def rollback(self):
        pass


def member_row(user_id, name, role=MemberRole.MEMBER):
    member = SimpleNamespace(user_id=user_id, role=role)
    profile = SimpleNamespace(full_name=name)
    return (member, profile)


async def _seed_location(redis, trip_id, user_id, lat, lon, speed=5.0, accuracy=8.0, age_seconds=2):
    recorded_at = (datetime.now(timezone.utc) - timedelta(seconds=age_seconds)).isoformat()
    await live_state_service.set_live_location(
        redis, trip_id, user_id, latitude=lat, longitude=lon, accuracy=accuracy, speed=speed, heading=None,
        recorded_at=recorded_at, updated_at=recorded_at,
    )
    await presence_service.mark_online(redis, trip_id, user_id)


# ---- compute_current_state -------------------------------------------


async def test_insufficient_data_with_fewer_than_two_members(fake_redis):
    db = FakeSession([member_row(USER_A, "Alice")])
    await _seed_location(fake_redis, TRIP_ID, USER_A, 32.30, 77.14)

    state = await engine.compute_current_state(db, fake_redis, TRIP_ID, GROUP_ID)

    assert state.group_state == "INSUFFICIENT_DATA"
    assert len(state.members) == 1
    assert state.members[0].name == "Alice"


async def test_moving_together_group_state(fake_redis):
    db = FakeSession([member_row(USER_A, "Alice"), member_row(USER_B, "Bob")])
    await _seed_location(fake_redis, TRIP_ID, USER_A, 32.30000, 77.14000)
    await _seed_location(fake_redis, TRIP_ID, USER_B, 32.30010, 77.14010)

    state = await engine.compute_current_state(db, fake_redis, TRIP_ID, GROUP_ID)

    assert state.group_state == "MOVING_TOGETHER"
    member_ids = {m.user_id for m in state.members}
    assert member_ids == {str(USER_A), str(USER_B)}


async def test_member_with_no_location_reports_stale_and_null_fields(fake_redis):
    db = FakeSession([member_row(USER_A, "Alice"), member_row(USER_B, "Bob")])
    await _seed_location(fake_redis, TRIP_ID, USER_A, 32.30, 77.14)
    # Bob is connected (online) but never sent a GPS point — STALE, not
    # OFFLINE, per the presence-vs-freshness distinction (movement.py).
    await presence_service.mark_online(fake_redis, TRIP_ID, USER_B)

    state = await engine.compute_current_state(db, fake_redis, TRIP_ID, GROUP_ID)
    bob = next(m for m in state.members if m.user_id == str(USER_B))

    assert bob.movement_state == "STALE"
    assert bob.latitude is None
    assert bob.distance_from_group_center_meters is None
    assert bob.is_isolated is False


async def test_offline_member_reported_as_offline(fake_redis):
    db = FakeSession([member_row(USER_A, "Alice")])
    # Location exists but presence was never marked online.
    recorded_at = datetime.now(timezone.utc).isoformat()
    await live_state_service.set_live_location(
        fake_redis, TRIP_ID, USER_A, latitude=32.3, longitude=77.14, accuracy=8, speed=1, heading=None,
        recorded_at=recorded_at, updated_at=recorded_at,
    )

    state = await engine.compute_current_state(db, fake_redis, TRIP_ID, GROUP_ID)

    assert state.members[0].presence == "OFFLINE"
    assert state.members[0].movement_state == "OFFLINE"


# ---- evaluate_and_persist_trip: locking -----------------------------------


async def test_concurrent_evaluations_do_not_both_run(fake_redis):
    """Two 'simultaneous' evaluations (e.g. two worker instances racing on
    the same trip) — the second must be skipped, not run twice."""
    db = FakeSession([member_row(USER_A, "Alice"), member_row(USER_B, "Bob")])
    await _seed_location(fake_redis, TRIP_ID, USER_A, 32.30, 77.14)
    await _seed_location(fake_redis, TRIP_ID, USER_B, 32.301, 77.141)

    first = await engine.evaluate_and_persist_trip(db, fake_redis, TRIP_ID, GROUP_ID)
    assert first is not None

    # Simulate a second evaluator racing in before the first released the
    # lock, by holding it manually.
    from app.core.redis_keys import intel_eval_lock_key

    await fake_redis.set(intel_eval_lock_key(TRIP_ID), "1", nx=True, px=30_000)
    second = await engine.evaluate_and_persist_trip(db, fake_redis, TRIP_ID, GROUP_ID)
    assert second is None  # skipped, lock held


async def test_lock_is_released_after_evaluation(fake_redis):
    from app.core.redis_keys import intel_eval_lock_key

    db = FakeSession([member_row(USER_A, "Alice")])
    await engine.evaluate_and_persist_trip(db, fake_redis, TRIP_ID, GROUP_ID)

    assert await fake_redis.exists(intel_eval_lock_key(TRIP_ID)) == 0


# ---- evaluate_and_persist_trip: persistence + WebSocket publish -----------


async def test_falling_behind_event_persisted_and_broadcast_over_websocket():
    """Pre-seeds the FALLING_BEHIND condition timer as already having
    persisted long enough (rather than waiting real wall-clock seconds in
    the test), then confirms the resulting event is both persisted and
    published to the trip's WebSocket channel."""
    import asyncio

    redis = fakeredis.FakeAsyncRedis(decode_responses=True)

    # Alice and Carol together (so the group center stays near them, not
    # drifting toward Bob) — Bob far enough from that center to trip
    # FALLING_BEHIND. With only 2 members the center would be the
    # midpoint, halving the effective distance, so this needs 3.
    USER_C = uuid.uuid4()
    db = FakeSession(
        [member_row(USER_A, "Alice"), member_row(USER_B, "Bob"), member_row(USER_C, "Carol")]
    )
    await _seed_location(redis, TRIP_ID, USER_A, 32.30000, 77.14000)
    await _seed_location(redis, TRIP_ID, USER_C, 32.30005, 77.14005)
    thresholds = current_thresholds()
    # ~1000m north of Alice/Carol. With 3 members the arithmetic-mean
    # center gets pulled toward Bob by ~1/3 of that, leaving him ~660m
    # from center — safely past FALLING_BEHIND_DISTANCE_METERS (500m).
    await _seed_location(redis, TRIP_ID, USER_B, 32.30900, 77.14000)

    # Pre-seed the condition timer as already past the duration threshold,
    # rather than waiting FALLING_BEHIND_DURATION_SECONDS of real wall
    # clock time in the test.
    stale_since = datetime.now(timezone.utc) - timedelta(seconds=thresholds.falling_behind_duration_seconds + 5)
    await redis.set(
        intel_condition_key(TRIP_ID, IntelligenceEventType.FALLING_BEHIND.value, str(USER_B)),
        json.dumps({"since": stale_since.isoformat()}),
    )

    manager = ConnectionManager()

    class _FakeWS:
        def __init__(self):
            self.sent = []

        async def send_text(self, text):
            self.sent.append(json.loads(text))

    listener = _FakeWS()
    # A real ConnectionManager instance, registered directly with the same
    # fakeredis client engine.py's publish_event() will PUBLISH to — this
    # is what actually proves the broadcast goes through Redis Pub/Sub,
    # not a direct call into any particular manager object.
    await manager.connect(redis, str(TRIP_ID), "some-listener", listener)

    computed = await engine.evaluate_and_persist_trip(db, redis, TRIP_ID, GROUP_ID)

    assert computed is not None
    assert any(r.event_type == IntelligenceEventType.FALLING_BEHIND and r.detected for r in computed.detection_results)

    for _ in range(20):
        if any(m.get("type") == "intelligence_event" for m in listener.sent):
            break
        await asyncio.sleep(0.05)

    intel_messages = [m for m in listener.sent if m["type"] == "intelligence_event"]
    assert len(intel_messages) >= 1
    falling_behind_msgs = [m for m in intel_messages if m["data"]["event_type"] == "FALLING_BEHIND"]
    assert len(falling_behind_msgs) == 1
    assert falling_behind_msgs[0]["data"]["user_id"] == str(USER_B)
    assert falling_behind_msgs[0]["data"]["resolved_at"] is None
