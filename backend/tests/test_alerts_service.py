"""
Alert Engine service tests against a fake DB session (no live database)
and fakeredis (dedup lock). Same FakeSession pattern as
test_intelligence_events.py.

Phase 12's notification hook (_notify_for_alert_sync, called from
apply_intelligence_event right after a create) is patched away here via
an autouse fixture — this file's FakeSession models a single alert-shaped
row, not a second Notification row a real notify() call would also
add/commit; notification behavior has its own dedicated suite
(test_notification_service.py), and the dashboard/composition-level tests
already cover the two working together.
"""

import uuid
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import patch

import fakeredis
import pytest
from sqlalchemy.exc import IntegrityError

import app.models  # noqa: F401 — registers every model before instantiation
from app.alerts import service as alerts_service
from app.models.enums import AlertStatus, AlertType, IntelligenceEventType, IntelligenceSeverity
from app.models.intelligence_event import IntelligenceEvent

TRIP_ID = uuid.uuid4()
GROUP_ID = uuid.uuid4()
USER_ID = uuid.uuid4()


@pytest.fixture(autouse=True)
def _stub_notifications():
    with patch("app.alerts.service._notify_for_alert_sync"):
        yield


class _ScalarResult:
    def __init__(self, value):
        self._value = value

    def first(self):
        return self._value


class FakeSession:
    def __init__(self, existing_alert=None):
        self._existing_alert = existing_alert
        self.commits = 0
        self.rollbacks = 0
        self._raise_integrity_next = False

    def scalars(self, stmt):
        return _ScalarResult(self._existing_alert)

    def add(self, obj):
        self._pending = obj

    def commit(self):
        if self._raise_integrity_next:
            self._raise_integrity_next = False
            raise IntegrityError("INSERT", {}, Exception("duplicate key"))
        self.commits += 1
        if getattr(self, "_pending", None) is not None:
            self._existing_alert = self._pending

    def rollback(self):
        self.rollbacks += 1

    def refresh(self, obj):
        if obj.id is None:
            obj.id = uuid.uuid4()
        if obj.created_at is None:
            obj.created_at = datetime.now(timezone.utc)


def make_event(event_type=IntelligenceEventType.FALLING_BEHIND, **overrides):
    event = IntelligenceEvent(
        id=uuid.uuid4(),
        trip_id=TRIP_ID,
        group_id=GROUP_ID,
        event_type=event_type,
        severity=IntelligenceSeverity.WARNING,
        user_id=USER_ID,
        related_user_id=None,
        latitude=22.7,
        longitude=75.8,
        event_metadata={"distance_meters": 650, "threshold_meters": 500},
    )
    for k, v in overrides.items():
        setattr(event, k, v)
    return event


def make_alert(**overrides):
    alert = SimpleNamespace(
        id=uuid.uuid4(),
        trip_id=TRIP_ID,
        event_id=None,
        alert_type=AlertType.FALLING_BEHIND,
        status=AlertStatus.ACTIVE,
        resolved_at=None,
        acknowledged_at=None,
        created_at=datetime.now(timezone.utc),
    )
    for k, v in overrides.items():
        setattr(alert, k, v)
    return alert


# ---- intelligence event -> alert creation ---------------------------------


async def test_intelligence_event_creates_alert(fake_redis):
    db = FakeSession(existing_alert=None)
    event = make_event()

    await alerts_service.apply_intelligence_event(db, fake_redis, event, "created")

    assert db.commits == 1
    assert db._existing_alert is not None
    assert db._existing_alert.status == AlertStatus.ACTIVE
    assert db._existing_alert.event_id == event.id
    assert db._existing_alert.alert_metadata == event.event_metadata


async def test_info_level_event_never_creates_an_alert(fake_redis):
    db = FakeSession(existing_alert=None)
    event = make_event(event_type=IntelligenceEventType.MOVING_TOGETHER, user_id=None)

    await alerts_service.apply_intelligence_event(db, fake_redis, event, "created")

    assert db.commits == 0


async def test_updated_action_never_creates_a_new_alert(fake_redis):
    """An intelligence event that's still active on this tick (metadata
    refreshed, not a fresh detection) must not spawn a second alert."""
    db = FakeSession(existing_alert=None)
    event = make_event()

    await alerts_service.apply_intelligence_event(db, fake_redis, event, "updated")

    assert db.commits == 0


async def test_noop_action_does_nothing(fake_redis):
    db = FakeSession(existing_alert=None)
    await alerts_service.apply_intelligence_event(db, fake_redis, None, "noop")
    assert db.commits == 0


async def test_concurrent_creation_for_same_event_is_deduplicated_via_redis_lock():
    """Two 'simultaneous' evaluations creating an alert for the same
    intelligence event — the Redis dedup lock stops the second from even
    attempting a DB insert."""
    redis = fakeredis.FakeAsyncRedis(decode_responses=True)
    event = make_event()
    db1 = FakeSession(existing_alert=None)
    db2 = FakeSession(existing_alert=None)

    await alerts_service.apply_intelligence_event(db1, redis, event, "created")
    await alerts_service.apply_intelligence_event(db2, redis, event, "created")

    assert db1.commits == 1
    assert db2.commits == 0


async def test_database_level_dedup_when_redis_lock_is_unavailable(fake_redis):
    """Even if two evaluations both win the Redis lock (e.g. it expired
    mid-race), the database's own partial unique index — simulated here
    via IntegrityError — is the real guarantee."""
    db = FakeSession(existing_alert=None)
    db._raise_integrity_next = True
    event = make_event()

    await alerts_service.apply_intelligence_event(db, fake_redis, event, "created")

    assert db.rollbacks == 1
    assert db._existing_alert is None


# ---- resolution -----------------------------------------------------------


async def test_resolved_intelligence_event_resolves_the_alert(fake_redis):
    alert = make_alert(status=AlertStatus.ACTIVE, resolved_at=None)
    db = FakeSession(existing_alert=alert)
    event = make_event()
    event.id = alert.event_id = uuid.uuid4()

    await alerts_service.apply_intelligence_event(db, fake_redis, event, "resolved")

    assert alert.resolved_at is not None
    assert alert.status == AlertStatus.RESOLVED


async def test_resolving_when_no_alert_exists_is_a_noop(fake_redis):
    db = FakeSession(existing_alert=None)
    event = make_event()

    await alerts_service.apply_intelligence_event(db, fake_redis, event, "resolved")

    assert db.commits == 0


# ---- acknowledge / resolve (REST-facing) -----------------------------------


def test_acknowledge_active_alert():
    db = FakeSession()
    alert = make_alert(status=AlertStatus.ACTIVE)

    updated = alerts_service.acknowledge_alert(db, alert)

    assert updated.status == AlertStatus.ACKNOWLEDGED
    assert updated.acknowledged_at is not None


def test_cannot_acknowledge_already_acknowledged_alert():
    from app.core.errors import AppHTTPException

    db = FakeSession()
    alert = make_alert(status=AlertStatus.ACKNOWLEDGED)

    with pytest.raises(AppHTTPException) as exc_info:
        alerts_service.acknowledge_alert(db, alert)
    assert exc_info.value.status_code == 409


def test_resolve_active_alert():
    db = FakeSession()
    alert = make_alert(status=AlertStatus.ACTIVE, resolved_at=None)

    updated = alerts_service.resolve_alert(db, alert)

    assert updated.status == AlertStatus.RESOLVED
    assert updated.resolved_at is not None


def test_resolve_acknowledged_alert_also_allowed():
    db = FakeSession()
    alert = make_alert(status=AlertStatus.ACKNOWLEDGED, resolved_at=None)

    updated = alerts_service.resolve_alert(db, alert)

    assert updated.status == AlertStatus.RESOLVED


def test_cannot_resolve_already_resolved_alert():
    from app.core.errors import AppHTTPException

    db = FakeSession()
    alert = make_alert(status=AlertStatus.RESOLVED, resolved_at=datetime.now(timezone.utc))

    with pytest.raises(AppHTTPException) as exc_info:
        alerts_service.resolve_alert(db, alert)
    assert exc_info.value.status_code == 409
