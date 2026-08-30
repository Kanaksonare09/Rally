"""
app/demo/data.py — the deterministic identity/geometry constants (the
part meaningfully unit-testable without a live database; the DB-writing
functions themselves — ensure_demo_group_sync, create_and_start_demo_trip_sync
— are thin compositions of already-tested group_service/trip_service/
route_service functions and are exercised end-to-end only via a live
database, same acknowledged limitation as every other DB-writing function
in this backend within this sandbox).
"""

import uuid

from app.demo import data as demo_data
from app.route.matcher import build_route_geometry
from app.schemas.route import RouteCreate


def test_demo_ids_are_deterministic_across_imports():
    """uuid5 with a fixed namespace+name always produces the same UUID —
    re-deriving it must match the module-level constant exactly."""
    assert demo_data.DEMO_GROUP_ID == uuid.uuid5(demo_data._NAMESPACE, "rally-demo-group")
    assert demo_data.DEMO_USER_IDS[0] == uuid.uuid5(demo_data._NAMESPACE, "rally-demo-member-0")


def test_exactly_four_demo_users_with_matching_names():
    assert len(demo_data.DEMO_USER_IDS) == 4
    assert len(demo_data.DEMO_USER_NAMES) == 4
    assert len(set(demo_data.DEMO_USER_IDS)) == 4  # all distinct


def test_demo_leader_is_the_first_demo_user():
    assert demo_data.DEMO_LEADER_ID == demo_data.DEMO_USER_IDS[0]


def test_demo_route_coordinates_are_valid_geojson_pairs():
    for lon, lat in demo_data.DEMO_ROUTE_COORDINATES:
        assert -180.0 <= lon <= 180.0
        assert -90.0 <= lat <= 90.0


def test_demo_route_coordinates_build_a_real_geometry():
    geometry = build_route_geometry(demo_data.DEMO_ROUTE_COORDINATES)
    assert geometry.total_distance_meters > 0


def test_demo_route_origin_destination_match_the_geometry_endpoints():
    """RouteCreate's own endpoint-tolerance validation (Phase 9) would
    reject a mismatch here — this is the same shape the real
    create_or_replace_route() call in create_and_start_demo_trip_sync
    uses, checked directly against the schema's own constraints."""
    data = RouteCreate(
        name="Demo Route",
        origin_latitude=demo_data.DEMO_ROUTE_ORIGIN[0], origin_longitude=demo_data.DEMO_ROUTE_ORIGIN[1],
        destination_latitude=demo_data.DEMO_ROUTE_DESTINATION[0], destination_longitude=demo_data.DEMO_ROUTE_DESTINATION[1],
        coordinates=demo_data.DEMO_ROUTE_COORDINATES,
    )
    assert data.coordinates[0] == demo_data.DEMO_ROUTE_COORDINATES[0]
