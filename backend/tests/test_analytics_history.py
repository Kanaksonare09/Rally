"""
app/analytics/history.py — trip history pagination/filtering and the
snapshot-first distance lookup for COMPLETED trips. FakeSession here
mirrors the rest of this codebase's established pattern of ignoring the
exact SQLAlchemy statement content and returning preset values — the
statement construction itself (select/where/subquery) is real SQLAlchemy
Core, always constructible without a live connection; only its execution
is faked.
"""

import uuid
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import patch

import app.models  # noqa: F401 — registers every model before instantiation
from app.analytics import history
from app.models.enums import TripStatus
from app.models.trip import Trip

GROUP_ID = uuid.uuid4()
USER_ID = uuid.uuid4()


class FakeSession:
    def __init__(self, rows, total):
        self._rows = rows
        self._total = total

    def scalar(self, stmt):
        return self._total

    def scalars(self, stmt):
        return SimpleNamespace(all=lambda: self._rows)


def make_trip_row(**overrides) -> Trip:
    trip = Trip(
        id=uuid.uuid4(), group_id=GROUP_ID, status=TripStatus.COMPLETED,
        started_at=datetime(2026, 8, 30, 10, 0, tzinfo=timezone.utc),
        ended_at=datetime(2026, 8, 30, 12, 0, tzinfo=timezone.utc),
        destination_name="Indore Ride",
    )
    for k, v in overrides.items():
        setattr(trip, k, v)
    return trip


# ---- _distance_for_history_item: snapshot-first --------------------------


@patch("app.analytics.history.get_snapshot")
def test_completed_trip_with_snapshot_uses_snapshot_distance(mock_snapshot):
    mock_snapshot.return_value = SimpleNamespace(distance_traveled_meters=58300.0)
    trip = make_trip_row(status=TripStatus.COMPLETED)

    distance = history._distance_for_history_item(None, trip)

    assert distance == 58300.0


@patch("app.analytics.history.queries.pick_representative_value")
@patch("app.analytics.history.queries.compute_distances_by_user")
@patch("app.analytics.history.queries.get_group_leader_id")
@patch("app.analytics.history.queries.fetch_location_points")
@patch("app.analytics.history.get_snapshot")
def test_completed_trip_without_snapshot_falls_back_to_live_computation(
    mock_snapshot, mock_points, mock_leader, mock_distances, mock_representative
):
    mock_snapshot.return_value = None
    mock_points.return_value = {"u1": [(1.0, 1.0, 5.0, datetime.now(timezone.utc))]}
    mock_leader.return_value = None
    mock_distances.return_value = {"u1": 500.0}
    mock_representative.return_value = 500.0
    trip = make_trip_row(status=TripStatus.COMPLETED)

    distance = history._distance_for_history_item(None, trip)

    assert distance == 500.0


@patch("app.analytics.history.get_snapshot")
@patch("app.analytics.history.queries.fetch_location_points")
def test_non_completed_trip_never_checks_snapshot(mock_points, mock_snapshot):
    mock_points.return_value = {}
    trip = make_trip_row(status=TripStatus.ACTIVE)

    history._distance_for_history_item(None, trip)

    mock_snapshot.assert_not_called()


@patch("app.analytics.history.queries.fetch_location_points")
def test_no_gps_history_at_all_returns_none(mock_points):
    mock_points.return_value = {}
    trip = make_trip_row(status=TripStatus.CREATED)

    assert history._distance_for_history_item(None, trip) is None


# ---- pagination / response shape ------------------------------------------


@patch("app.analytics.history.queries.list_active_group_members")
@patch("app.analytics.history._distance_for_history_item")
def test_paginate_wraps_rows_with_total_limit_offset(mock_distance, mock_members):
    mock_distance.return_value = None
    mock_members.return_value = []
    rows = [make_trip_row(), make_trip_row()]
    db = FakeSession(rows=rows, total=20)

    result = history.list_group_trip_history(db, GROUP_ID, limit=2, offset=4)

    assert result.total == 20
    assert result.limit == 2
    assert result.offset == 4
    assert len(result.items) == 2


@patch("app.analytics.history.queries.list_active_group_members")
@patch("app.analytics.history._distance_for_history_item")
def test_empty_history_returns_empty_items_not_error(mock_distance, mock_members):
    mock_distance.return_value = None
    mock_members.return_value = []
    db = FakeSession(rows=[], total=0)

    result = history.list_user_trip_history(db, USER_ID, limit=20, offset=0)

    assert result.items == []
    assert result.total == 0


@patch("app.analytics.history.queries.list_active_group_members")
@patch("app.analytics.history._distance_for_history_item")
def test_history_item_uses_destination_name_as_display_name(mock_distance, mock_members):
    mock_distance.return_value = None
    mock_members.return_value = [1, 2, 3]
    trip = make_trip_row(destination_name="Manali Ride")
    db = FakeSession(rows=[trip], total=1)

    result = history.list_group_trip_history(db, GROUP_ID, limit=20, offset=0)

    assert result.items[0].name == "Manali Ride"
    assert result.items[0].member_count == 3
