"""
app/route/service.py: route CRUD/validation (fake DB session, no live
Postgres — same FakeSession pattern as test_trip_service.py) and live
progress computation (fakeredis).
"""

import uuid
from datetime import datetime, timezone
from types import SimpleNamespace

import pytest

import app.models  # noqa: F401 — registers every model before instantiation
from app.core.errors import AppHTTPException
from app.models.enums import RouteStatus, TripStatus
from app.route import service as route_service
from app.schemas.route import RouteCreate

TRIP_ID = uuid.uuid4()

VALID_ROUTE = RouteCreate(
    name="Manali trip",
    origin_latitude=12.90,
    origin_longitude=77.0,
    destination_latitude=12.91,
    destination_longitude=77.0,
    coordinates=[[77.0, 12.90], [77.0, 12.905], [77.0, 12.91]],
    estimated_duration_seconds=600,
)


class FakeScalarResult:
    def __init__(self, value):
        self._value = value

    def first(self):
        return self._value


class FakeSession:
    def __init__(self, existing_route=None):
        self.added = []
        self.committed = False
        self.refreshed = []
        self._existing_route = existing_route

    def scalars(self, stmt):
        return FakeScalarResult(self._existing_route)

    def add(self, obj):
        self.added.append(obj)
        self._existing_route = obj

    def commit(self):
        self.committed = True

    def refresh(self, obj):
        self.refreshed.append(obj)
        if obj.id is None:
            obj.id = uuid.uuid4()
        if getattr(obj, "created_at", None) is None:
            obj.created_at = datetime.now(timezone.utc)
        if getattr(obj, "updated_at", None) is None:
            obj.updated_at = datetime.now(timezone.utc)


def make_trip(status=TripStatus.CREATED) -> SimpleNamespace:
    return SimpleNamespace(id=TRIP_ID, status=status)


# ---- create_or_replace_route: validation ----------------------------------


def test_route_can_only_be_created_while_trip_is_created():
    db = FakeSession()
    trip = make_trip(status=TripStatus.ACTIVE)
    with pytest.raises(AppHTTPException) as exc_info:
        route_service.create_or_replace_route(db, trip, VALID_ROUTE)
    assert exc_info.value.status_code == 409
    assert exc_info.value.code == "INVALID_TRIP_STATE"


def test_degenerate_geometry_is_rejected():
    db = FakeSession()
    trip = make_trip()
    degenerate = VALID_ROUTE.model_copy(update={"coordinates": [[77.0, 12.9], [77.0, 12.9]]})
    with pytest.raises(AppHTTPException) as exc_info:
        route_service.create_or_replace_route(db, trip, degenerate)
    assert exc_info.value.code == "INVALID_ROUTE_GEOMETRY"


def test_origin_far_from_geometry_start_is_rejected():
    db = FakeSession()
    trip = make_trip()
    bad_origin = VALID_ROUTE.model_copy(update={"origin_latitude": 12.95})  # ~5.5km away, way past 200m tolerance
    with pytest.raises(AppHTTPException) as exc_info:
        route_service.create_or_replace_route(db, trip, bad_origin)
    assert exc_info.value.code == "INVALID_ROUTE_GEOMETRY"


def test_destination_far_from_geometry_end_is_rejected():
    db = FakeSession()
    trip = make_trip()
    bad_destination = VALID_ROUTE.model_copy(update={"destination_latitude": 12.80})
    with pytest.raises(AppHTTPException) as exc_info:
        route_service.create_or_replace_route(db, trip, bad_destination)
    assert exc_info.value.code == "INVALID_ROUTE_GEOMETRY"


# ---- create_or_replace_route: happy path + server-authoritative distance --


def test_valid_route_is_created_as_planned():
    db = FakeSession()
    trip = make_trip()

    route = route_service.create_or_replace_route(db, trip, VALID_ROUTE)

    assert route.status == RouteStatus.PLANNED
    assert route.trip_id == TRIP_ID
    assert db.committed is True
    assert route in db.added


def test_distance_meters_is_server_calculated_not_trusted_from_client():
    """RouteCreate has no distance_meters field at all — this test's real
    purpose is documenting that the server always derives it from
    `coordinates`, never accepts a client-supplied value."""
    assert not hasattr(VALID_ROUTE, "distance_meters")
    db = FakeSession()
    route = route_service.create_or_replace_route(db, make_trip(), VALID_ROUTE)
    assert route.distance_meters > 0


def test_coordinates_are_stored_as_given():
    db = FakeSession()
    route = route_service.create_or_replace_route(db, make_trip(), VALID_ROUTE)
    assert route.coordinates == VALID_ROUTE.coordinates


# ---- create_or_replace_route: replace-in-place -----------------------------


def test_replacing_a_planned_route_updates_the_same_row():
    existing = SimpleNamespace(
        id=uuid.uuid4(), trip_id=TRIP_ID, status=RouteStatus.PLANNED, created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    db = FakeSession(existing_route=existing)

    updated_data = VALID_ROUTE.model_copy(update={"name": "Rerouted"})
    route = route_service.create_or_replace_route(db, make_trip(), updated_data)

    assert route is existing
    assert route.name == "Rerouted"
    assert db.added == []  # never a second row


def test_replacing_a_non_planned_route_is_rejected():
    existing = SimpleNamespace(id=uuid.uuid4(), trip_id=TRIP_ID, status=RouteStatus.ACTIVE)
    db = FakeSession(existing_route=existing)

    with pytest.raises(AppHTTPException) as exc_info:
        route_service.create_or_replace_route(db, make_trip(), VALID_ROUTE)
    assert exc_info.value.status_code == 409
    assert exc_info.value.code == "ROUTE_NOT_REPLACEABLE"


# ---- lifecycle transitions --------------------------------------------------


def test_activate_route_moves_planned_to_active():
    existing = SimpleNamespace(id=uuid.uuid4(), trip_id=TRIP_ID, status=RouteStatus.PLANNED)
    db = FakeSession(existing_route=existing)
    route = route_service.activate_route_sync(db, TRIP_ID)
    assert route.status == RouteStatus.ACTIVE


def test_activate_route_is_a_noop_with_no_route():
    db = FakeSession(existing_route=None)
    assert route_service.activate_route_sync(db, TRIP_ID) is None
    assert db.committed is False


def test_activate_route_is_a_noop_if_not_planned():
    existing = SimpleNamespace(id=uuid.uuid4(), trip_id=TRIP_ID, status=RouteStatus.ACTIVE)
    db = FakeSession(existing_route=existing)
    route = route_service.activate_route_sync(db, TRIP_ID)
    assert route.status == RouteStatus.ACTIVE  # unchanged
    assert db.committed is False


def test_complete_route_moves_active_to_completed():
    existing = SimpleNamespace(id=uuid.uuid4(), trip_id=TRIP_ID, status=RouteStatus.ACTIVE)
    db = FakeSession(existing_route=existing)
    route = route_service.complete_route_sync(db, TRIP_ID)
    assert route.status == RouteStatus.COMPLETED


def test_cancel_route_moves_planned_to_cancelled():
    existing = SimpleNamespace(id=uuid.uuid4(), trip_id=TRIP_ID, status=RouteStatus.PLANNED)
    db = FakeSession(existing_route=existing)
    route = route_service.cancel_route_sync(db, TRIP_ID)
    assert route.status == RouteStatus.CANCELLED


# ---- live progress computation ---------------------------------------------


def make_route(**overrides) -> SimpleNamespace:
    route = SimpleNamespace(
        id=uuid.uuid4(),
        trip_id=TRIP_ID,
        coordinates=[[77.0, 12.90], [77.0, 12.91]],
        distance_meters=1112.0,
        estimated_duration_seconds=600,
        status=RouteStatus.ACTIVE,
    )
    for k, v in overrides.items():
        setattr(route, k, v)
    return route


async def test_online_member_with_fresh_location_gets_a_match(fake_redis):
    route = make_route()
    members = [{"user_id": "u1", "name": "Alice", "role": "LEADER"}]
    now = datetime(2026, 8, 30, 12, 0, 0, tzinfo=timezone.utc)
    live_locations = {"u1": {"latitude": 12.905, "longitude": 77.0, "recorded_at": now.isoformat(), "speed": 5.0}}
    online_status = {"u1": True}

    results, group_fraction, trip_arrived = await route_service.compute_route_progress(
        fake_redis, TRIP_ID, route, members, live_locations, online_status, now
    )

    assert results[0].match is not None
    assert results[0].route_state is not None
    assert group_fraction == pytest.approx(results[0].match.route_fraction)
    assert trip_arrived is False


async def test_offline_member_is_excluded_from_group_median(fake_redis):
    route = make_route()
    members = [
        {"user_id": "u1", "name": "Alice", "role": "LEADER"},
        {"user_id": "u2", "name": "Bob", "role": "MEMBER"},
    ]
    now = datetime(2026, 8, 30, 12, 0, 0, tzinfo=timezone.utc)
    live_locations = {"u1": {"latitude": 12.905, "longitude": 77.0, "recorded_at": now.isoformat(), "speed": 5.0}}
    online_status = {"u1": True, "u2": False}  # u2 offline, no location either

    results, group_fraction, trip_arrived = await route_service.compute_route_progress(
        fake_redis, TRIP_ID, route, members, live_locations, online_status, now
    )

    u2_result = next(r for r in results if r.user_id == "u2")
    assert u2_result.match is None
    assert u2_result.route_state is None
    assert group_fraction is not None  # still computed from u1 alone


async def test_stale_location_is_treated_as_unusable(fake_redis):
    route = make_route()
    members = [{"user_id": "u1", "name": "Alice", "role": "LEADER"}]
    now = datetime(2026, 8, 30, 12, 0, 0, tzinfo=timezone.utc)
    live_locations = {
        "u1": {
            "latitude": 12.905, "longitude": 77.0,
            "recorded_at": (now.replace(hour=11)).isoformat(), "speed": 5.0,
        }
    }
    online_status = {"u1": True}

    results, group_fraction, trip_arrived = await route_service.compute_route_progress(
        fake_redis, TRIP_ID, route, members, live_locations, online_status, now
    )

    assert results[0].match is None
    assert group_fraction is None
