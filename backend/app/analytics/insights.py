"""
Trip insights — GET /trips/{trip_id}/insights. Plain, deterministic
sentences generated from the exact same aggregated numbers
GET /trips/{trip_id}/analytics already computes (reused directly, never
re-derived a second way) — no LLM, no narrative generation, no
fabrication. A highlight is only ever added when its underlying number is
not None; missing data produces fewer highlights, never a vague or made-up
one.
"""

from typing import List

from sqlalchemy.orm import Session

from app.analytics import queries
from app.analytics.snapshot import get_snapshot, snapshot_to_trip_analytics
from app.analytics.trip_analytics import compute_trip_analytics
from app.models.enums import TripStatus
from app.models.trip import Trip
from app.schemas.analytics import TripAnalytics, TripInsights, TripInsightsStatistics


def _get_analytics(db: Session, trip: Trip) -> TripAnalytics:
    if trip.status == TripStatus.COMPLETED:
        snapshot = get_snapshot(db, trip.id)
        if snapshot is not None:
            return snapshot_to_trip_analytics(trip, snapshot)
    return compute_trip_analytics(db, trip, source="live")


def _member_participation(db: Session, trip: Trip) -> tuple:
    """(total active group members, how many actually sent at least one
    GPS point on this trip) — the raw counts a participation highlight is
    built from."""
    members = queries.list_active_group_members(db, trip.group_id)
    points_by_user = queries.fetch_location_points(db, trip.id)
    active_participants = sum(1 for m in members if str(m["user_id"]) in points_by_user)
    return len(members), active_participants


def build_trip_insights(db: Session, trip: Trip) -> TripInsights:
    analytics = _get_analytics(db, trip)
    member_count, active_participants = _member_participation(db, trip)

    highlights: List[str] = []

    if analytics.route_available and analytics.route_completion_percent is not None:
        highlights.append(f"The group completed {analytics.route_completion_percent:.0f}% of the planned route.")

    if analytics.distance_traveled_meters is not None:
        km = analytics.distance_traveled_meters / 1000
        highlights.append(f"The group traveled approximately {km:.1f} km.")

    if analytics.duration_seconds is not None and analytics.duration_seconds > 0:
        hours = analytics.duration_seconds / 3600
        highlights.append(f"The trip lasted about {hours:.1f} hours." if hours >= 1 else f"The trip lasted about {analytics.duration_seconds // 60} minutes.")

    if analytics.route_deviations > 0:
        highlights.append(
            f"The group experienced {analytics.route_deviations} route deviation"
            f"{'s' if analytics.route_deviations != 1 else ''}."
        )
    elif analytics.route_available:
        highlights.append("The group stayed on the planned route the entire trip.")

    if analytics.sos_count > 0:
        highlights.append(f"{analytics.sos_count} SOS emergenc{'y was' if analytics.sos_count == 1 else 'ies were'} triggered during the trip.")
    elif trip.status == TripStatus.COMPLETED:
        highlights.append("All members finished the trip safely — no SOS emergencies were triggered.")

    if analytics.critical_alerts_count > 0:
        highlights.append(f"{analytics.critical_alerts_count} critical alert{'s' if analytics.critical_alerts_count != 1 else ''} occurred during the trip.")
    elif analytics.alerts_count > 0:
        highlights.append(f"{analytics.alerts_count} alert{'s' if analytics.alerts_count != 1 else ''} occurred, none critical.")

    if member_count > 0:
        highlights.append(
            f"{active_participants} of {member_count} group members shared live location during the trip."
        )

    return TripInsights(
        trip_id=trip.id,
        highlights=highlights,
        statistics=TripInsightsStatistics(
            distance_meters=analytics.distance_traveled_meters,
            duration_seconds=analytics.duration_seconds,
            route_completion_percent=analytics.route_completion_percent,
            alerts=analytics.alerts_count,
            sos=analytics.sos_count,
            route_deviations=analytics.route_deviations,
            member_count=member_count,
            active_member_count=active_participants,
        ),
    )
