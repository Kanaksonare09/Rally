"""
app/analytics/snapshot.py — idempotent completed-trip analytics snapshot
generation, against a fake DB session (no live database).
"""

import uuid
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from sqlalchemy.exc import IntegrityError

import app.models  # noqa: F401 — registers every model before instantiation
from app.analytics import snapshot as snapshot_module
from app.schemas.analytics import TripAnalytics

TRIP_ID = uuid.uuid4()


class _ScalarResult:
    def __init__(self, value):
        self._value = value

    def first(self):
        return self._value


class FakeSession:
    def __init__(self, existing_snapshot=None, raise_integrity_on_commit=False):
        self._existing_snapshot = existing_snapshot
        self._raise_integrity_on_commit = raise_integrity_on_commit
        self.commits = 0
        self.added = []

    def scalars(self, stmt):
        return _ScalarResult(self._existing_snapshot)

    def add(self, obj):
        self.added.append(obj)

    def commit(self):
        if self._raise_integrity_on_commit:
            self._raise_integrity_on_commit = False
            raise IntegrityError("INSERT", {}, Exception("duplicate key"))
        self.commits += 1
        if self.added:
            self._existing_snapshot = self.added[-1]

    def rollback(self):
        pass

    def refresh(self, obj):
        if getattr(obj, "id", None) is None:
            obj.id = uuid.uuid4()


def make_trip(**overrides):
    trip = SimpleNamespace(id=TRIP_ID, group_id=uuid.uuid4())
    for k, v in overrides.items():
        setattr(trip, k, v)
    return trip


def make_analytics(**overrides) -> TripAnalytics:
    defaults = dict(
        trip_id=TRIP_ID, status="COMPLETED", started_at=None, ended_at=None, duration_seconds=7200,
        member_count=4, distance_traveled_meters=58300.0, route_available=True,
        planned_distance_meters=60000.0, route_completion_percent=97.2,
        alerts_count=3, critical_alerts_count=0, sos_count=0, route_deviations=2, source="live",
    )
    defaults.update(overrides)
    return TripAnalytics(**defaults)


@patch("app.analytics.snapshot.compute_trip_analytics")
def test_generates_a_new_snapshot_when_none_exists(mock_compute):
    mock_compute.return_value = make_analytics()
    db = FakeSession(existing_snapshot=None)

    result = snapshot_module.generate_snapshot(db, make_trip())

    assert result.trip_id == TRIP_ID
    assert result.duration_seconds == 7200
    assert result.distance_traveled_meters == 58300.0
    assert db.commits == 1


@patch("app.analytics.snapshot.compute_trip_analytics")
def test_existing_snapshot_is_reused_not_recomputed(mock_compute):
    existing = SimpleNamespace(id=uuid.uuid4(), trip_id=TRIP_ID)
    db = FakeSession(existing_snapshot=existing)

    result = snapshot_module.generate_snapshot(db, make_trip())

    assert result is existing
    assert db.commits == 0
    mock_compute.assert_not_called()


@patch("app.analytics.snapshot.compute_trip_analytics")
def test_concurrent_generation_dedups_via_database_constraint(mock_compute):
    """Two 'simultaneous' end-trip calls both pass the initial lookup —
    only the database's own UNIQUE(trip_id) constraint (simulated here via
    IntegrityError) prevents a second row."""
    mock_compute.return_value = make_analytics()
    db = FakeSession(existing_snapshot=None, raise_integrity_on_commit=True)

    # Winner already committed a snapshot the "get existing" lookup will
    # see once we simulate the race resolving.
    winner_snapshot = SimpleNamespace(id=uuid.uuid4(), trip_id=TRIP_ID)

    original_scalars = db.scalars

    call_count = {"n": 0}

    def scalars_with_race(stmt):
        call_count["n"] += 1
        if call_count["n"] == 1:
            return _ScalarResult(None)  # first lookup: nothing yet
        return _ScalarResult(winner_snapshot)  # second lookup (after IntegrityError): winner's row

    db.scalars = scalars_with_race

    result = snapshot_module.generate_snapshot(db, make_trip())

    assert result is winner_snapshot


@patch("app.analytics.snapshot.compute_trip_analytics")
def test_generate_snapshot_safely_swallows_errors(mock_compute):
    """Trip completion must never fail because snapshot generation did."""
    mock_compute.side_effect = RuntimeError("boom")
    db = FakeSession(existing_snapshot=None)

    snapshot_module.generate_snapshot_safely(db, make_trip())  # must not raise


def test_snapshot_to_trip_analytics_preserves_snapshot_values():
    trip = make_trip()
    trip.status = SimpleNamespace(value="COMPLETED")
    trip.started_at = datetime(2026, 8, 30, 10, 0, tzinfo=timezone.utc)
    trip.ended_at = datetime(2026, 8, 30, 12, 0, tzinfo=timezone.utc)

    snapshot = SimpleNamespace(
        duration_seconds=7200, member_count=4, distance_traveled_meters=58300.0,
        planned_distance_meters=60000.0, completion_percent=97.2,
        alerts_count=3, critical_alerts_count=0, sos_count=0, route_deviations=2,
    )

    result = snapshot_module.snapshot_to_trip_analytics(trip, snapshot)

    assert result.source == "snapshot"
    assert result.route_available is True
    assert result.distance_traveled_meters == 58300.0


def test_snapshot_to_trip_analytics_no_route_is_unavailable_not_zero():
    trip = make_trip()
    trip.status = SimpleNamespace(value="COMPLETED")
    trip.started_at = None
    trip.ended_at = None

    snapshot = SimpleNamespace(
        duration_seconds=None, member_count=2, distance_traveled_meters=None,
        planned_distance_meters=None, completion_percent=None,
        alerts_count=0, critical_alerts_count=0, sos_count=0, route_deviations=0,
    )

    result = snapshot_module.snapshot_to_trip_analytics(trip, snapshot)

    assert result.route_available is False
    assert result.planned_distance_meters is None
