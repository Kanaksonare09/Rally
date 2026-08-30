import pytest

from app.intelligence.group_analysis import MemberPosition, analyze_group, cluster_by_distance

# A small tight cluster near Manali, plus a reference point ~1.3km away
NEAR_1 = (32.3072, 77.1481)
NEAR_2 = (32.3073, 77.1482)
NEAR_3 = (32.3071, 77.1480)
FAR = (32.3172, 77.1561)

DEFAULTS = dict(
    min_accuracy_meters=100.0,
    isolated_distance_meters=1000.0,
    separation_distance_meters=800.0,
    cohesion_distance_meters=300.0,
)


def moving(user_id, point, accuracy=10.0):
    return MemberPosition(user_id=user_id, latitude=point[0], longitude=point[1], accuracy=accuracy, movement_state="MOVING")


def test_group_center_calculated_correctly():
    positions = [moving("a", NEAR_1), moving("b", NEAR_2), moving("c", NEAR_3)]
    result = analyze_group(positions, **DEFAULTS)
    expected_lat = (NEAR_1[0] + NEAR_2[0] + NEAR_3[0]) / 3
    expected_lon = (NEAR_1[1] + NEAR_2[1] + NEAR_3[1]) / 3
    assert result.center == pytest.approx((expected_lat, expected_lon))


def test_stale_members_excluded_from_center():
    stale = MemberPosition(user_id="stale", latitude=0, longitude=0, accuracy=10, movement_state="STALE")
    positions = [moving("a", NEAR_1), moving("b", NEAR_2), stale]
    result = analyze_group(positions, **DEFAULTS)
    assert "stale" not in result.eligible_member_ids
    # Center should be near NEAR_1/NEAR_2, nowhere near (0, 0)
    assert result.center[0] > 30


def test_offline_members_excluded_from_center():
    offline = MemberPosition(user_id="offline", latitude=0, longitude=0, accuracy=10, movement_state="OFFLINE")
    positions = [moving("a", NEAR_1), moving("b", NEAR_2), offline]
    result = analyze_group(positions, **DEFAULTS)
    assert "offline" not in result.eligible_member_ids


def test_poor_accuracy_members_excluded():
    imprecise = MemberPosition(user_id="bad_gps", latitude=0, longitude=0, accuracy=500.0, movement_state="MOVING")
    positions = [moving("a", NEAR_1), imprecise]
    result = analyze_group(positions, min_accuracy_meters=100.0, isolated_distance_meters=1000, separation_distance_meters=800, cohesion_distance_meters=300)
    assert "bad_gps" not in result.eligible_member_ids


def test_members_with_no_location_get_a_null_analysis_entry():
    """analyze_group only receives members who *have* a position, but the
    caller (engine.py) still needs an entry for every member — verify the
    all-None fallback path used for non-usable-but-present positions."""
    stale = MemberPosition(user_id="stale", latitude=1, longitude=1, accuracy=10, movement_state="STALE")
    positions = [moving("a", NEAR_1), stale]
    result = analyze_group(positions, **DEFAULTS)
    assert result.members["stale"].distance_from_center_meters is None
    assert result.members["stale"].is_isolated is False


def test_group_moving_together_is_cohesive():
    positions = [moving("a", NEAR_1), moving("b", NEAR_2), moving("c", NEAR_3)]
    result = analyze_group(positions, **DEFAULTS)
    assert result.is_cohesive is True
    assert len(result.clusters) == 1


def test_group_separation_detected_as_two_clusters():
    positions = [moving("a", NEAR_1), moving("b", NEAR_2), moving("d", FAR)]
    result = analyze_group(positions, **DEFAULTS)
    assert len(result.clusters) == 2
    assert result.is_cohesive is False
    # Main (larger) cluster first
    assert set(result.clusters[0]) == {"a", "b"}
    assert result.clusters[1] == ["d"]


def test_isolated_member_detected():
    """Matches the spec's own worked example: A is far from everyone,
    B/C/D are close to each other."""
    positions = [
        moving("A", (0.0, 0.0)),
        moving("B", (0.02, 0.0)),  # far from A
        moving("C", (0.0201, 0.0001)),  # close to B
        moving("D", (0.0199, -0.0001)),  # close to B/C
    ]
    result = analyze_group(
        positions, min_accuracy_meters=100, isolated_distance_meters=1000,
        separation_distance_meters=100000, cohesion_distance_meters=100000,
    )
    assert result.members["A"].is_isolated is True
    assert result.members["B"].is_isolated is False
    assert result.members["C"].is_isolated is False
    assert result.members["D"].is_isolated is False


def test_non_isolated_members_have_no_false_positive():
    positions = [moving("a", NEAR_1), moving("b", NEAR_2), moving("c", NEAR_3)]
    result = analyze_group(positions, **DEFAULTS)
    assert all(not m.is_isolated for m in result.members.values())


def test_isolation_requires_at_least_one_other_member():
    result = analyze_group([moving("solo", NEAR_1)], **DEFAULTS)
    assert result.members["solo"].is_isolated is False


def test_cluster_by_distance_single_cluster():
    positions = [moving("a", NEAR_1), moving("b", NEAR_2)]
    clusters = cluster_by_distance(positions, linkage_distance_meters=500)
    assert len(clusters) == 1
    assert set(clusters[0]) == {"a", "b"}


def test_cluster_by_distance_transitively_links_members():
    """a-b close, b-c close, a-c not directly close — still one cluster
    via the transitive union-find linkage."""
    mid = ((NEAR_1[0] + FAR[0]) / 2, (NEAR_1[1] + FAR[1]) / 2)
    positions = [moving("a", NEAR_1), moving("mid", mid), moving("c", FAR)]
    clusters = cluster_by_distance(positions, linkage_distance_meters=800)
    assert len(clusters) == 1
