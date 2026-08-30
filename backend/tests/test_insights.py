"""
app/analytics/insights.py — highlights are only generated when the
underlying number actually exists; nothing is fabricated. Patches
compute_trip_analytics (the same aggregated numbers
GET /trips/{trip_id}/analytics already returns) rather than re-deriving
anything, plus the member-participation query.
"""

import uuid
from types import SimpleNamespace
from unittest.mock import patch

from app.analytics.insights import build_trip_insights
from app.models.enums import TripStatus
from app.schemas.analytics import TripAnalytics

TRIP_ID = uuid.uuid4()
GROUP_ID = uuid.uuid4()
USER_A = uuid.uuid4()


def make_trip(status=TripStatus.COMPLETED):
    return SimpleNamespace(id=TRIP_ID, group_id=GROUP_ID, status=status)


def make_analytics(**overrides) -> TripAnalytics:
    base = dict(
        trip_id=TRIP_ID, status="COMPLETED", started_at=None, ended_at=None, duration_seconds=7200,
        member_count=4, distance_traveled_meters=58300.0, route_available=True, planned_distance_meters=60000.0,
        route_completion_percent=97.2, alerts_count=3, critical_alerts_count=0, sos_count=0, route_deviations=2,
        source="live",
    )
    base.update(overrides)
    return TripAnalytics(**base)


def _run(analytics, members=None, points=None):
    with patch("app.analytics.insights.compute_trip_analytics", return_value=analytics), \
         patch("app.analytics.insights.get_snapshot", return_value=None), \
         patch("app.analytics.insights.queries.list_active_group_members", return_value=members or []), \
         patch("app.analytics.insights.queries.fetch_location_points", return_value=points or {}):
        return build_trip_insights(db=None, trip=make_trip())


def test_route_completion_highlight_present_when_available():
    result = _run(make_analytics())
    assert any("97%" in h for h in result.highlights)


def test_no_route_produces_no_completion_highlight():
    result = _run(make_analytics(route_available=False, route_completion_percent=None, planned_distance_meters=None))
    assert not any("planned route" in h for h in result.highlights)


def test_route_deviation_highlight_pluralized_correctly():
    result = _run(make_analytics(route_deviations=2))
    assert any("2 route deviations" in h for h in result.highlights)

    result_one = _run(make_analytics(route_deviations=1))
    assert any("1 route deviation." in h for h in result_one.highlights)


def test_zero_deviations_reports_stayed_on_route():
    result = _run(make_analytics(route_deviations=0, route_available=True))
    assert any("stayed on the planned route" in h for h in result.highlights)


def test_sos_zero_and_completed_reports_safe_completion():
    result = _run(make_analytics(sos_count=0), )
    assert any("safely" in h for h in result.highlights)


def test_sos_present_reports_it_not_safe_completion():
    result = _run(make_analytics(sos_count=1))
    assert any("SOS emergency was" in h for h in result.highlights)
    assert not any("safely" in h for h in result.highlights)


def test_missing_distance_produces_no_distance_highlight():
    result = _run(make_analytics(distance_traveled_meters=None))
    assert not any("traveled approximately" in h for h in result.highlights)


def test_member_participation_highlight():
    members = [{"user_id": USER_A}, {"user_id": uuid.uuid4()}]
    points = {str(USER_A): [(0.0, 0.0, None, None)]}
    result = _run(make_analytics(), members=members, points=points)
    assert any("1 of 2 group members" in h for h in result.highlights)
    assert result.statistics.member_count == 2
    assert result.statistics.active_member_count == 1


def test_statistics_mirror_analytics_numbers():
    analytics = make_analytics()
    result = _run(analytics)
    assert result.statistics.distance_meters == analytics.distance_traveled_meters
    assert result.statistics.duration_seconds == analytics.duration_seconds
    assert result.statistics.alerts == analytics.alerts_count
    assert result.statistics.sos == analytics.sos_count
    assert result.statistics.route_deviations == analytics.route_deviations


def test_no_data_at_all_produces_minimal_but_no_fake_highlights():
    empty = make_analytics(
        distance_traveled_meters=None, duration_seconds=None, route_available=False,
        route_completion_percent=None, planned_distance_meters=None, route_deviations=0,
        alerts_count=0, critical_alerts_count=0, sos_count=0,
    )
    result = _run(empty)
    # Only the deterministic "no data available" facts should appear —
    # never an invented distance/duration sentence.
    assert not any("traveled approximately" in h for h in result.highlights)
    assert not any("lasted about" in h for h in result.highlights)
