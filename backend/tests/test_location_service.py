"""
Unit tests for GPS ingestion business logic, using a fake/capturing Session
instead of a real Postgres connection — no live database in this
environment (see backend README). Filter/order/limit construction is
verified by compiling the SQLAlchemy statement (with literal binds) rather
than executing it, so the query-building logic is checked without a DB.
"""

import uuid
from datetime import datetime, timedelta, timezone

import pytest
from pydantic import ValidationError

import app.models  # noqa: F401 — registers every model before instantiation
from app.core.errors import AppHTTPException
from app.models.enums import TripStatus
from app.models.trip import Trip
from app.schemas.location import LocationCreate, LocationHistoryQuery
from app.services import location_service

GROUP_ID = uuid.uuid4()
TRIP_ID = uuid.uuid4()
USER_ID = uuid.uuid4()


class FakeSession:
    def __init__(self):
        self.added = []
        self.committed = False

    def add(self, obj):
        self.added.append(obj)

    def commit(self):
        self.committed = True

    def refresh(self, obj):
        pass


class CapturingSession:
    """Records the statement passed to scalars() without executing it."""

    def __init__(self):
        self.last_stmt = None

    def scalars(self, stmt):
        self.last_stmt = stmt

        class _Result:
            def all(_self):
                return []

        return _Result()


def compiled_sql(stmt) -> str:
    return str(stmt.compile(compile_kwargs={"literal_binds": True}))


def make_trip(status: TripStatus = TripStatus.ACTIVE) -> Trip:
    return Trip(id=TRIP_ID, group_id=GROUP_ID, status=status)


# ---- record_location: trip state -----------------------------------------


def test_record_location_accepted_for_active_trip():
    trip = make_trip(TripStatus.ACTIVE)
    db = FakeSession()

    location = location_service.record_location(
        db, trip, USER_ID, LocationCreate(latitude=22.7196, longitude=75.8577)
    )

    assert db.committed is True
    assert location.trip_id == TRIP_ID
    assert location.group_id == GROUP_ID
    assert location.user_id == USER_ID


@pytest.mark.parametrize("status", [TripStatus.CREATED, TripStatus.COMPLETED, TripStatus.CANCELLED])
def test_record_location_rejected_for_non_active_trip(status):
    trip = make_trip(status)
    db = FakeSession()

    with pytest.raises(AppHTTPException) as exc_info:
        location_service.record_location(db, trip, USER_ID, LocationCreate(latitude=1, longitude=1))

    assert exc_info.value.status_code == 409
    assert exc_info.value.code == "INVALID_TRIP_STATE"
    assert db.committed is False


# ---- record_location: trusted fields --------------------------------------


def test_group_id_and_user_id_are_never_taken_from_the_request():
    """LocationCreate has no group_id/user_id field at all — group_id comes
    from trip.group_id, user_id from the authenticated caller passed in by
    the router. This asserts the stored row reflects that, not any
    client-controlled value."""
    trip = make_trip()
    db = FakeSession()

    location = location_service.record_location(
        db, trip, USER_ID, LocationCreate(latitude=1, longitude=1)
    )

    assert location.group_id == trip.group_id
    assert location.user_id == USER_ID


def test_point_is_built_as_longitude_latitude():
    trip = make_trip()
    db = FakeSession()

    location = location_service.record_location(
        db, trip, USER_ID, LocationCreate(latitude=22.7196, longitude=75.8577)
    )

    assert location.location == "POINT(75.8577 22.7196)"


# ---- record_location: timestamps -----------------------------------------


def test_recorded_at_defaults_to_now_when_omitted():
    trip = make_trip()
    db = FakeSession()
    before = datetime.now(timezone.utc)

    location = location_service.record_location(db, trip, USER_ID, LocationCreate(latitude=1, longitude=1))

    after = datetime.now(timezone.utc)
    assert before <= location.recorded_at <= after


def test_naive_recorded_at_is_normalized_to_utc():
    trip = make_trip()
    db = FakeSession()
    naive = (datetime.now(timezone.utc) - timedelta(hours=1)).replace(tzinfo=None)

    location = location_service.record_location(
        db, trip, USER_ID, LocationCreate(latitude=1, longitude=1, recorded_at=naive)
    )

    assert location.recorded_at.tzinfo is not None


def test_recorded_at_far_in_the_future_is_rejected():
    trip = make_trip()
    db = FakeSession()
    future = datetime.now(timezone.utc) + timedelta(hours=1)

    with pytest.raises(AppHTTPException) as exc_info:
        location_service.record_location(
            db, trip, USER_ID, LocationCreate(latitude=1, longitude=1, recorded_at=future)
        )

    assert exc_info.value.status_code == 400
    assert exc_info.value.code == "INVALID_TIMESTAMP"


def test_small_clock_drift_is_tolerated():
    trip = make_trip()
    db = FakeSession()
    slightly_future = datetime.now(timezone.utc) + timedelta(seconds=30)

    location = location_service.record_location(
        db, trip, USER_ID, LocationCreate(latitude=1, longitude=1, recorded_at=slightly_future)
    )

    assert location.recorded_at == slightly_future


def test_old_recorded_at_is_accepted_out_of_order_delivery():
    """Mobile networks can deliver stale points late — an old recorded_at
    must not be rejected just for being in the past."""
    trip = make_trip()
    db = FakeSession()
    old = datetime.now(timezone.utc) - timedelta(hours=3)

    location = location_service.record_location(
        db, trip, USER_ID, LocationCreate(latitude=1, longitude=1, recorded_at=old)
    )

    assert location.recorded_at == old


# ---- record_location: optional fields -------------------------------------


def test_optional_fields_are_stored_when_provided():
    trip = make_trip()
    db = FakeSession()

    location = location_service.record_location(
        db, trip, USER_ID,
        LocationCreate(latitude=1, longitude=1, accuracy=8.5, speed=12.4, heading=180.0),
    )

    assert location.accuracy == 8.5
    assert location.speed == 12.4
    assert location.heading == 180.0


def test_optional_fields_default_to_none():
    trip = make_trip()
    db = FakeSession()

    location = location_service.record_location(db, trip, USER_ID, LocationCreate(latitude=1, longitude=1))

    assert location.accuracy is None
    assert location.speed is None
    assert location.heading is None


# ---- LocationCreate schema validation --------------------------------------


@pytest.mark.parametrize("latitude", [90.1, -90.1])
def test_schema_rejects_invalid_latitude(latitude):
    with pytest.raises(ValidationError):
        LocationCreate(latitude=latitude, longitude=0)


@pytest.mark.parametrize("longitude", [180.1, -180.1])
def test_schema_rejects_invalid_longitude(longitude):
    with pytest.raises(ValidationError):
        LocationCreate(latitude=0, longitude=longitude)


def test_schema_rejects_negative_accuracy():
    with pytest.raises(ValidationError):
        LocationCreate(latitude=0, longitude=0, accuracy=-0.1)


def test_schema_rejects_negative_speed():
    with pytest.raises(ValidationError):
        LocationCreate(latitude=0, longitude=0, speed=-0.1)


@pytest.mark.parametrize("heading", [-0.1, 360, 360.1])
def test_schema_rejects_invalid_heading(heading):
    with pytest.raises(ValidationError):
        LocationCreate(latitude=0, longitude=0, heading=heading)


def test_schema_accepts_boundary_heading_values():
    LocationCreate(latitude=0, longitude=0, heading=0)
    LocationCreate(latitude=0, longitude=0, heading=359.9)


def test_location_create_has_no_trusted_fields():
    """id/trip_id/group_id/user_id/created_at must never be client-settable."""
    forbidden = {"id", "trip_id", "group_id", "user_id", "created_at"}
    assert forbidden.isdisjoint(LocationCreate.model_fields.keys())


def test_location_history_query_enforces_maximum_limit():
    with pytest.raises(ValidationError):
        LocationHistoryQuery(limit=5001)


def test_location_history_query_enforces_minimum_limit():
    with pytest.raises(ValidationError):
        LocationHistoryQuery(limit=0)


def test_location_history_query_default_limit_is_500():
    assert LocationHistoryQuery().limit == 500


# ---- get_location_history: query construction ------------------------------


def test_history_query_orders_by_recorded_at_ascending():
    db = CapturingSession()
    location_service.get_location_history(db, TRIP_ID, LocationHistoryQuery())
    assert "ORDER BY location_history.recorded_at ASC" in compiled_sql(db.last_stmt)


def test_history_query_scopes_to_the_given_trip():
    db = CapturingSession()
    location_service.get_location_history(db, TRIP_ID, LocationHistoryQuery())
    # literal-bind rendering drops the UUID's hyphens, so compare hex forms
    assert TRIP_ID.hex in compiled_sql(db.last_stmt).replace("-", "")


def test_history_query_applies_limit():
    db = CapturingSession()
    location_service.get_location_history(db, TRIP_ID, LocationHistoryQuery(limit=50))
    assert "LIMIT 50" in compiled_sql(db.last_stmt)


def test_history_query_filters_by_user_id_when_given():
    db = CapturingSession()
    target_user = uuid.uuid4()
    location_service.get_location_history(db, TRIP_ID, LocationHistoryQuery(user_id=target_user, limit=10))
    assert target_user.hex in compiled_sql(db.last_stmt).replace("-", "")


def test_history_query_supports_cursor_pagination():
    db = CapturingSession()
    cursor = datetime(2026, 8, 26, 12, 0, 0, tzinfo=timezone.utc)
    location_service.get_location_history(db, TRIP_ID, LocationHistoryQuery(cursor=cursor, limit=10))
    sql = compiled_sql(db.last_stmt)
    assert "location_history.recorded_at >" in sql


def test_history_query_supports_from_to_range():
    db = CapturingSession()
    from_time = datetime(2026, 8, 26, 0, 0, 0, tzinfo=timezone.utc)
    to_time = datetime(2026, 8, 26, 23, 59, 59, tzinfo=timezone.utc)
    location_service.get_location_history(
        db, TRIP_ID, LocationHistoryQuery(from_time=from_time, to_time=to_time, limit=10)
    )
    sql = compiled_sql(db.last_stmt)
    assert "location_history.recorded_at >=" in sql
    assert "location_history.recorded_at <=" in sql
