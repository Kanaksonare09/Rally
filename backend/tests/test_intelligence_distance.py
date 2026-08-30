import pytest

from app.intelligence.distance import group_center, haversine_distance_meters, max_pairwise_distance_meters

# Manali area coordinates, matching the mock data used elsewhere in this project
A = (32.3072, 77.1481)
B = (32.3172, 77.1561)


def test_same_coordinate_returns_approximately_zero():
    d = haversine_distance_meters(A[0], A[1], A[0], A[1])
    assert d == pytest.approx(0.0, abs=0.01)


def test_known_coordinates_return_reasonable_distance():
    # ~1.3km apart per the project's own mock data comment (geo.ts)
    d = haversine_distance_meters(A[0], A[1], B[0], B[1])
    assert 1000 < d < 1600


def test_distance_is_symmetric():
    d1 = haversine_distance_meters(A[0], A[1], B[0], B[1])
    d2 = haversine_distance_meters(B[0], B[1], A[0], A[1])
    assert d1 == pytest.approx(d2)


@pytest.mark.parametrize(
    "lat,lon",
    [(91, 0), (-91, 0), (0, 181), (0, -181), (float("nan"), 0), (0, float("inf"))],
)
def test_invalid_coordinates_raise_value_error(lat, lon):
    with pytest.raises(ValueError):
        haversine_distance_meters(lat, lon, 0, 0)
    with pytest.raises(ValueError):
        haversine_distance_meters(0, 0, lat, lon)


def test_group_center_is_arithmetic_mean():
    points = [(22.7000, 75.8500), (22.7100, 75.8600), (22.7050, 75.8550)]
    center = group_center(points)
    assert center == pytest.approx((22.7050, 75.8550))


def test_group_center_of_empty_list_is_none():
    assert group_center([]) is None


def test_group_center_of_single_point_is_that_point():
    assert group_center([A]) == pytest.approx(A)


def test_max_pairwise_distance_of_single_point_is_zero():
    assert max_pairwise_distance_meters([A]) == 0.0


def test_max_pairwise_distance_of_empty_list_is_zero():
    assert max_pairwise_distance_meters([]) == 0.0


def test_max_pairwise_distance_finds_the_farthest_pair():
    close_pair_and_far_point = [A, (A[0] + 0.0001, A[1] + 0.0001), B]
    result = max_pairwise_distance_meters(close_pair_and_far_point)
    assert result == pytest.approx(haversine_distance_meters(A[0], A[1], B[0], B[1]), rel=0.01)
