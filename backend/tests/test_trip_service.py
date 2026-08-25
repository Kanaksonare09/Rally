"""
Unit tests for trip lifecycle business logic, using a fake Session instead
of a real Postgres connection — there's no live Supabase database available
in this environment (see backend README / final validation notes).

`import app.models` at the top guarantees every model class is registered
on the shared SQLAlchemy registry before any model is instantiated here —
Trip's relationships reference LocationHistory/Alert/SOSEvent by string
name, which only resolve once those classes have been imported somewhere
in the process (see the auth.users shadow-table fix in Phase 2 for the
same underlying gotcha).
"""

import uuid

import pytest
from sqlalchemy.exc import IntegrityError

import app.models  # noqa: F401
from app.core.errors import AppHTTPException
from app.models.enums import TripStatus
from app.models.trip import Trip
from app.schemas.trip import TripCreate, TripStart
from app.services import trip_service

GROUP_ID = uuid.uuid4()
USER_ID = uuid.uuid4()
LEADER_ID = uuid.uuid4()


class FakeScalarResult:
    def __init__(self, value):
        self._value = value

    def first(self):
        return self._value


class FakeSession:
    def __init__(self, active_trip_conflict=None, raise_integrity_on_commit=False):
        self.added = []
        self.committed = False
        self.rolled_back = False
        self.refreshed = []
        self._active_trip_conflict = active_trip_conflict
        self._raise_integrity_on_commit = raise_integrity_on_commit

    def add(self, obj):
        self.added.append(obj)

    def scalars(self, stmt):
        return FakeScalarResult(self._active_trip_conflict)

    def commit(self):
        if self._raise_integrity_on_commit:
            raise IntegrityError("UPDATE trips ...", {}, Exception("duplicate key value"))
        self.committed = True

    def refresh(self, obj):
        self.refreshed.append(obj)

    def rollback(self):
        self.rolled_back = True

    def get(self, model, pk):
        return None


def make_trip(status: TripStatus = TripStatus.CREATED, **overrides) -> Trip:
    trip = Trip(
        id=uuid.uuid4(),
        group_id=GROUP_ID,
        started_by=USER_ID,
        status=status,
        destination_name="Solang Valley",
    )
    for key, value in overrides.items():
        setattr(trip, key, value)
    return trip


# ---- create_trip -----------------------------------------------------


def test_create_trip_starts_in_created_status():
    db = FakeSession()
    trip = trip_service.create_trip(db, GROUP_ID, USER_ID, TripCreate(destination_name="Rohtang Pass"))

    assert trip.status == TripStatus.CREATED
    assert trip.started_by == USER_ID
    assert trip.group_id == GROUP_ID
    assert trip.destination_name == "Rohtang Pass"
    assert db.committed is True


def test_create_trip_started_by_always_comes_from_authenticated_user():
    """There is no client-controllable field in TripCreate that could ever
    become started_by — the parameter is passed in directly by the caller
    (the router), never read off the request body."""
    db = FakeSession()
    trip = trip_service.create_trip(db, GROUP_ID, USER_ID, TripCreate())
    assert trip.started_by == USER_ID


def test_create_trip_rejects_partial_coordinates():
    db = FakeSession()
    with pytest.raises(AppHTTPException) as exc_info:
        trip_service.create_trip(db, GROUP_ID, USER_ID, TripCreate(latitude=32.3167))
    assert exc_info.value.status_code == 400
    assert exc_info.value.code == "INVALID_LOCATION"


def test_create_trip_with_full_coordinates_builds_point():
    db = FakeSession()
    trip = trip_service.create_trip(
        db, GROUP_ID, USER_ID, TripCreate(latitude=32.3167, longitude=77.1553)
    )
    assert trip.destination == "POINT(77.1553 32.3167)"


# ---- start_trip --------------------------------------------------------


def test_start_trip_moves_created_to_active_and_sets_started_at():
    trip = make_trip(status=TripStatus.CREATED)
    db = FakeSession()

    result = trip_service.start_trip(db, trip, None)

    assert result.status == TripStatus.ACTIVE
    assert result.started_at is not None
    assert db.committed is True


def test_start_trip_saves_optional_start_location():
    trip = make_trip(status=TripStatus.CREATED)
    db = FakeSession()

    trip_service.start_trip(db, trip, TripStart(latitude=32.2396, longitude=77.1887))

    assert trip.start_location == "POINT(77.1887 32.2396)"


@pytest.mark.parametrize("status", [TripStatus.ACTIVE, TripStatus.COMPLETED, TripStatus.CANCELLED])
def test_start_trip_rejects_non_created_source_state(status):
    trip = make_trip(status=status)
    db = FakeSession()

    with pytest.raises(AppHTTPException) as exc_info:
        trip_service.start_trip(db, trip, None)

    assert exc_info.value.status_code == 409
    assert exc_info.value.code == "INVALID_TRIP_STATE"


def test_start_trip_rejects_when_group_already_has_active_trip():
    trip = make_trip(status=TripStatus.CREATED)
    other_active_trip = make_trip(status=TripStatus.ACTIVE, id=uuid.uuid4())
    db = FakeSession(active_trip_conflict=other_active_trip)

    with pytest.raises(AppHTTPException) as exc_info:
        trip_service.start_trip(db, trip, None)

    assert exc_info.value.status_code == 409
    assert exc_info.value.code == "ACTIVE_TRIP_EXISTS"


def test_start_trip_converts_db_race_into_active_trip_exists():
    """Simulates two concurrent start requests both passing the app-level
    pre-check, with the second one losing to the database's partial unique
    index at commit time."""
    trip = make_trip(status=TripStatus.CREATED)
    db = FakeSession(active_trip_conflict=None, raise_integrity_on_commit=True)

    with pytest.raises(AppHTTPException) as exc_info:
        trip_service.start_trip(db, trip, None)

    assert exc_info.value.status_code == 409
    assert exc_info.value.code == "ACTIVE_TRIP_EXISTS"
    assert db.rolled_back is True


# ---- end_trip ------------------------------------------------------------


def test_end_trip_moves_active_to_completed_and_sets_ended_at():
    trip = make_trip(status=TripStatus.ACTIVE)
    db = FakeSession()

    result = trip_service.end_trip(db, trip)

    assert result.status == TripStatus.COMPLETED
    assert result.ended_at is not None


@pytest.mark.parametrize("status", [TripStatus.CREATED, TripStatus.COMPLETED, TripStatus.CANCELLED])
def test_end_trip_rejects_non_active_source_state(status):
    trip = make_trip(status=status)
    db = FakeSession()

    with pytest.raises(AppHTTPException) as exc_info:
        trip_service.end_trip(db, trip)

    assert exc_info.value.status_code == 409
    assert exc_info.value.code == "INVALID_TRIP_STATE"


# ---- cancel_trip ---------------------------------------------------------


def test_cancel_trip_moves_created_to_cancelled():
    trip = make_trip(status=TripStatus.CREATED)
    db = FakeSession()

    result = trip_service.cancel_trip(db, trip)

    assert result.status == TripStatus.CANCELLED


@pytest.mark.parametrize("status", [TripStatus.ACTIVE, TripStatus.COMPLETED, TripStatus.CANCELLED])
def test_cancel_trip_rejects_non_created_source_state(status):
    trip = make_trip(status=status)
    db = FakeSession()

    with pytest.raises(AppHTTPException) as exc_info:
        trip_service.cancel_trip(db, trip)

    assert exc_info.value.status_code == 409
    assert exc_info.value.code == "INVALID_TRIP_STATE"
