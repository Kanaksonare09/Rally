import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import pytest

from app.intelligence import worker


def test_worker_status_is_starting_before_any_tick():
    worker._last_tick_completed_at = None
    assert worker.worker_health_status() == "starting"


def test_worker_status_is_ok_shortly_after_a_tick():
    worker._last_tick_completed_at = datetime.now(timezone.utc)
    assert worker.worker_health_status() == "ok"


def test_worker_status_is_stalled_when_far_overdue(monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, "INTELLIGENCE_EVALUATION_INTERVAL_SECONDS", 3.0)
    worker._last_tick_completed_at = datetime.now(timezone.utc) - timedelta(seconds=1000)
    assert worker.worker_health_status() == "stalled"


async def test_evaluation_tick_returns_zero_without_redis(monkeypatch):
    from app.core.database import SessionLocal as real_session_local

    with patch("app.intelligence.worker.get_redis", side_effect=RuntimeError("no redis")):
        count = await worker.run_evaluation_tick()
    assert count == 0


async def test_evaluation_tick_returns_zero_without_database(monkeypatch):
    with patch("app.intelligence.worker.SessionLocal", None):
        count = await worker.run_evaluation_tick()
    assert count == 0


async def test_evaluation_tick_evaluates_every_active_trip(fake_redis):
    trip_a, trip_b = uuid.uuid4(), uuid.uuid4()
    group_a, group_b = uuid.uuid4(), uuid.uuid4()

    class FakeSession:
        def close(self):
            pass

    evaluated = []

    async def fake_evaluate(db, redis, trip_id, group_id):
        evaluated.append(trip_id)
        return None

    with patch("app.intelligence.worker.get_redis", return_value=fake_redis), \
         patch("app.intelligence.worker.SessionLocal", return_value=FakeSession()), \
         patch("app.intelligence.worker._active_trips_sync", return_value=[(trip_a, group_a), (trip_b, group_b)]), \
         patch("app.intelligence.worker.evaluate_and_persist_trip", side_effect=fake_evaluate):
        count = await worker.run_evaluation_tick()

    assert count == 2
    assert set(evaluated) == {trip_a, trip_b}


async def test_evaluation_tick_continues_after_one_trip_fails(fake_redis):
    trip_a, trip_b = uuid.uuid4(), uuid.uuid4()

    class FakeSession:
        def close(self):
            pass

    async def flaky_evaluate(db, redis, trip_id, group_id):
        if trip_id == trip_a:
            raise RuntimeError("boom")
        return None

    with patch("app.intelligence.worker.get_redis", return_value=fake_redis), \
         patch("app.intelligence.worker.SessionLocal", return_value=FakeSession()), \
         patch("app.intelligence.worker._active_trips_sync", return_value=[(trip_a, uuid.uuid4()), (trip_b, uuid.uuid4())]), \
         patch("app.intelligence.worker.evaluate_and_persist_trip", side_effect=flaky_evaluate):
        count = await worker.run_evaluation_tick()

    # trip_a failed but trip_b still got evaluated — one bad trip must
    # never take down the whole tick.
    assert count == 1
