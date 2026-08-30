"""
Pure-function tests for app/route/matcher.py — no DB, no Redis. Coordinates
throughout are [longitude, latitude] (GeoJSON order), matching the
convention documented in that module; distances are cross-checked against
app.intelligence.distance.haversine_distance_meters directly so nothing
here depends on a "known good" magic number.
"""

import pytest

from app.intelligence.distance import haversine_distance_meters
from app.route.matcher import build_route_geometry, match_point_to_route

# A short, straight route (~1.1km) running due north near the equator,
# small enough that Shapely's planar (lon, lat) projection and real-world
# Haversine distance agree to well within a meter.
STRAIGHT_ROUTE = [[77.0, 12.90], [77.0, 12.91]]


def test_build_route_geometry_rejects_fewer_than_two_points():
    with pytest.raises(ValueError):
        build_route_geometry([[77.0, 12.9]])


def test_build_route_geometry_rejects_zero_length_route():
    with pytest.raises(ValueError):
        build_route_geometry([[77.0, 12.9], [77.0, 12.9]])


def test_build_route_geometry_total_distance_matches_haversine():
    geometry = build_route_geometry(STRAIGHT_ROUTE)
    expected = haversine_distance_meters(12.90, 77.0, 12.91, 77.0)
    assert geometry.total_distance_meters == pytest.approx(expected, rel=1e-6)


def test_build_route_geometry_cumulative_distances_are_monotonic():
    route = [[77.0, 12.90], [77.0, 12.905], [77.0, 12.91]]
    geometry = build_route_geometry(route)
    assert geometry.cumulative_distances_meters == sorted(geometry.cumulative_distances_meters)
    assert geometry.cumulative_distances_meters[0] == 0.0
    assert geometry.cumulative_distances_meters[-1] == pytest.approx(geometry.total_distance_meters)


def test_match_at_origin_reports_zero_progress():
    geometry = build_route_geometry(STRAIGHT_ROUTE)
    match = match_point_to_route(geometry, latitude=12.90, longitude=77.0)
    assert match.distance_from_route_meters == pytest.approx(0.0, abs=1.0)
    assert match.route_fraction == pytest.approx(0.0, abs=0.01)
    assert match.distance_traveled_meters == pytest.approx(0.0, abs=1.0)
    assert match.distance_remaining_meters == pytest.approx(geometry.total_distance_meters, abs=1.0)


def test_match_at_destination_reports_full_progress():
    geometry = build_route_geometry(STRAIGHT_ROUTE)
    match = match_point_to_route(geometry, latitude=12.91, longitude=77.0)
    assert match.distance_from_route_meters == pytest.approx(0.0, abs=1.0)
    assert match.route_fraction == pytest.approx(1.0, abs=0.01)
    assert match.distance_remaining_meters == pytest.approx(0.0, abs=1.0)


def test_match_midpoint_on_the_line():
    geometry = build_route_geometry(STRAIGHT_ROUTE)
    match = match_point_to_route(geometry, latitude=12.905, longitude=77.0)
    assert match.distance_from_route_meters == pytest.approx(0.0, abs=1.0)
    assert match.route_fraction == pytest.approx(0.5, abs=0.02)


def test_match_off_to_the_side_reports_nonzero_distance():
    geometry = build_route_geometry(STRAIGHT_ROUTE)
    # ~0.001 degrees of longitude at this latitude is roughly 100m+.
    match = match_point_to_route(geometry, latitude=12.905, longitude=77.001)
    assert match.distance_from_route_meters > 50.0


def test_traveled_plus_remaining_equals_total():
    geometry = build_route_geometry(STRAIGHT_ROUTE)
    match = match_point_to_route(geometry, latitude=12.905, longitude=77.0005)
    assert match.distance_traveled_meters + match.distance_remaining_meters == pytest.approx(
        geometry.total_distance_meters, abs=1.0
    )


def test_multi_segment_route_matches_nearest_segment_not_just_the_first():
    """An L-shaped route: a point near the far leg must match against
    that leg, not incorrectly project onto the first one."""
    route = [[77.0, 12.90], [77.0, 12.91], [77.01, 12.91]]
    geometry = build_route_geometry(route)
    match = match_point_to_route(geometry, latitude=12.91, longitude=77.005)
    assert match.distance_from_route_meters == pytest.approx(0.0, abs=5.0)
    # Past the first leg's full length, somewhere into the second leg.
    first_leg_length = geometry.cumulative_distances_meters[1]
    assert match.distance_traveled_meters > first_leg_length


def test_point_far_from_entire_route_still_returns_nearest_match():
    geometry = build_route_geometry(STRAIGHT_ROUTE)
    match = match_point_to_route(geometry, latitude=13.5, longitude=78.0)
    assert match.distance_from_route_meters > 1000.0
    assert 0.0 <= match.route_fraction <= 1.0
