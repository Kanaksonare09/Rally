"""
Integration tests for Phase 9's route evaluation, layered on top of
evaluate_and_persist_trip() (app/intelligence/engine.py::_evaluate_route).
Same FakeSession-plus-fakeredis approach as test_intelligence_engine.py,
extended so a single fake session can also answer the Route lookup
(app/route/service.py::get_route_by_trip) alongside the existing
IntelligenceEvent/Alert queries — discriminated by which ORM entity the
statement is actually selecting.
"""

import asyncio
import json
import uuid
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import fakeredis

from app.core.redis_keys import intel_condition_key
from app.intelligence import engine
from app.models.enums import IntelligenceEventType, MemberRole, RouteStatus
from app.models.route import Route
from app.services import live_state_service, presence_service
from app.websocket.manager import ConnectionManager

TRIP_ID = uuid.uuid4()
GROUP_ID = uuid.uuid4()
ROUTE_ID = uuid.uuid4()
USER_A = uuid.uuid4()


class _ExecuteResult:
    def __init__(self, rows):
        self._rows = rows

    def all(self):
        return self._rows


class _ScalarResult:
    def __init__(self, value=None):
        self._value = value

    def first(self):
        return self._value


class RouteAwareFakeSession:
    """Same shape as test_intelligence_engine.py's FakeSession, extended to
    also serve `select(Route)...` — everything else (IntelligenceEvent /
    Alert existing-active-row checks) keeps returning "nothing exists yet"
    exactly like that file's version, since this module only cares about
    the route-specific path."""

    def __init__(self, member_rows, route):
        self._member_rows = member_rows
        self._route = route

    def execute(self, stmt):
        return _ExecuteResult(self._member_rows)

    def scalars(self, stmt):
        entity = stmt.column_descriptions[0]["entity"]
        if entity is Route:
            return _ScalarResult(self._route)
        return _ScalarResult(None)

    def add(self, obj):
        pass

    def commit(self):
        pass

    def refresh(self, obj):
        if getattr(obj, "id", "unset") is None:
            obj.id = uuid.uuid4()
        for attr in ("detected_at", "created_at"):
            if getattr(obj, attr, "unset") is None:
                setattr(obj, attr, datetime.now(timezone.utc))

    def rollback(self):
        pass


def member_row(user_id, name, role=MemberRole.MEMBER):
    return (SimpleNamespace(user_id=user_id, role=role), SimpleNamespace(full_name=name))


def make_route(**overrides) -> SimpleNamespace:
    route = SimpleNamespace(
        id=ROUTE_ID, trip_id=TRIP_ID,
        coordinates=[[77.14000, 32.30000], [77.14000, 32.31000]],
        distance_meters=1112.0, estimated_duration_seconds=600, status=RouteStatus.ACTIVE,
    )
    for k, v in overrides.items():
        setattr(route, k, v)
    return route


async def _seed_location(redis, trip_id, user_id, lat, lon, speed=5.0, age_seconds=2):
    recorded_at = (datetime.now(timezone.utc) - timedelta(seconds=age_seconds)).isoformat()
    await live_state_service.set_live_location(
        redis, trip_id, user_id, latitude=lat, longitude=lon, accuracy=8.0, speed=speed, heading=None,
        recorded_at=recorded_at, updated_at=recorded_at,
    )
    await presence_service.mark_online(redis, trip_id, user_id)


async def test_no_route_is_a_complete_noop(fake_redis):
    """A trip with no route must evaluate exactly as it did before Phase
    9 existed — same assertion test_intelligence_engine.py's own tests
    already make, restated here to pin the no-route case explicitly."""
    db = RouteAwareFakeSession([member_row(USER_A, "Alice")], route=None)
    await _seed_location(fake_redis, TRIP_ID, USER_A, 32.30000, 77.14000)

    computed = await engine.evaluate_and_persist_trip(db, fake_redis, TRIP_ID, GROUP_ID)
    assert computed is not None


async def test_planned_route_is_not_evaluated_yet():
    """Only an ACTIVE route is matched against — a route that's still
    PLANNED (trip hasn't started) has no live locations to make sense of."""
    redis = fakeredis.FakeAsyncRedis(decode_responses=True)
    db = RouteAwareFakeSession([member_row(USER_A, "Alice")], route=make_route(status=RouteStatus.PLANNED))
    await _seed_location(redis, TRIP_ID, USER_A, 32.30000, 77.14000)

    manager = ConnectionManager()

    class _FakeWS:
        def __init__(self):
            self.sent = []

        async def send_text(self, text):
            self.sent.append(json.loads(text))

    listener = _FakeWS()
    await manager.connect(redis, str(TRIP_ID), "listener", listener)

    await engine.evaluate_and_persist_trip(db, redis, TRIP_ID, GROUP_ID)
    await asyncio.sleep(0.1)

    assert not any(m.get("type") == "route_progress" for m in listener.sent)


async def test_active_route_publishes_route_progress_every_tick():
    redis = fakeredis.FakeAsyncRedis(decode_responses=True)
    db = RouteAwareFakeSession([member_row(USER_A, "Alice", role=MemberRole.LEADER)], route=make_route())
    # Roughly 30% along the route (a straight ~1.1km line north).
    await _seed_location(redis, TRIP_ID, USER_A, 32.30300, 77.14000)

    manager = ConnectionManager()

    class _FakeWS:
        def __init__(self):
            self.sent = []

        async def send_text(self, text):
            self.sent.append(json.loads(text))

    listener = _FakeWS()
    await manager.connect(redis, str(TRIP_ID), "listener", listener)

    computed = await engine.evaluate_and_persist_trip(db, redis, TRIP_ID, GROUP_ID)
    assert computed is not None

    for _ in range(20):
        if any(m.get("type") == "route_progress" for m in listener.sent):
            break
        await asyncio.sleep(0.05)

    progress_msgs = [m for m in listener.sent if m["type"] == "route_progress"]
    assert len(progress_msgs) == 1
    data = progress_msgs[0]["data"]
    assert data["trip_id"] == str(TRIP_ID)
    assert data["route_id"] == str(ROUTE_ID)
    assert 0.0 < data["group_route_fraction"] < 1.0
    assert data["members"][0]["user_id"] == str(USER_A)


async def test_persistent_off_route_creates_intelligence_event_and_alert():
    redis = fakeredis.FakeAsyncRedis(decode_responses=True)
    db = RouteAwareFakeSession([member_row(USER_A, "Alice")], route=make_route())
    # ~0.003 deg of longitude at this latitude (~280m) is well past a
    # 100m OFF_ROUTE_THRESHOLD_METERS for a route running due north.
    await _seed_location(redis, TRIP_ID, USER_A, 32.30300, 77.143)

    from app.intelligence.thresholds import current_thresholds

    thresholds = current_thresholds()
    # ROUTE_DEVIATION is a real IntelligenceEventType (see detectors.py),
    # so its persistence timer lives under intel_condition_key, not
    # route_condition_key (which only backs the ephemeral ARRIVED
    # debounce in app/route/progress.py) — pre-seed it as already past
    # the duration threshold, same trick test_intelligence_engine.py uses
    # for FALLING_BEHIND.
    stale_since = datetime.now(timezone.utc) - timedelta(seconds=thresholds.route_deviation_duration_seconds + 5)
    await redis.set(
        intel_condition_key(TRIP_ID, IntelligenceEventType.ROUTE_DEVIATION.value, str(USER_A)),
        json.dumps({"since": stale_since.isoformat()}),
    )

    manager = ConnectionManager()

    class _FakeWS:
        def __init__(self):
            self.sent = []

        async def send_text(self, text):
            self.sent.append(json.loads(text))

    listener = _FakeWS()
    await manager.connect(redis, str(TRIP_ID), "listener", listener)

    await engine.evaluate_and_persist_trip(db, redis, TRIP_ID, GROUP_ID)

    for _ in range(20):
        if any(m.get("type") == "route_deviation" for m in listener.sent):
            break
        await asyncio.sleep(0.05)

    deviation_msgs = [m for m in listener.sent if m["type"] == "route_deviation"]
    assert len(deviation_msgs) == 1
    assert deviation_msgs[0]["data"]["status"] == "DEVIATED"
    assert deviation_msgs[0]["data"]["user_id"] == str(USER_A)

    # Same seam as every other detector: created/resolved must also reach
    # the generic intelligence_event frame and (via the alert policy
    # table) an alert frame.
    intel_msgs = [m for m in listener.sent if m["type"] == "intelligence_event"]
    assert any(m["data"]["event_type"] == "ROUTE_DEVIATION" for m in intel_msgs)
    alert_msgs = [m for m in listener.sent if m["type"] == "alert"]
    assert any(m["data"]["alert_type"] == "ROUTE_DEVIATION" for m in alert_msgs)
