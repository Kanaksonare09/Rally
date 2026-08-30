"""Trip-level headline analytics — GET /trips/{trip_id}/analytics.

For a COMPLETED trip, `app/analytics/snapshot.py` may serve this from
`trip_analytics_snapshots` instead of recomputing it — see that module
and the `source` field on TripAnalytics. This module is the "compute it
fresh" path both the live case and snapshot generation itself call into.
"""

from sqlalchemy.orm import Session

from app.alerts import service as alerts_service
from app.analytics import queries
from app.analytics.route_analytics import build_route_analytics
from app.core.config import settings
from app.intelligence import events as intelligence_events
from app.models.enums import IntelligenceEventType
from app.models.trip import Trip
from app.schemas.analytics import TripAnalytics
from app.sos import service as sos_service


def compute_trip_analytics(db: Session, trip: Trip, *, source: str = "live") -> TripAnalytics:
    duration_seconds = queries.compute_trip_duration_seconds(trip)
    members = queries.list_active_group_members(db, trip.group_id)
    leader_id = queries.get_group_leader_id(db, trip.group_id)

    points_by_user = queries.fetch_location_points(db, trip.id)
    distances_by_user = queries.compute_distances_by_user(
        points_by_user, max_speed_mps=settings.MAX_ANALYTICS_SPEED_MPS, max_accuracy_meters=settings.MIN_USABLE_ACCURACY_METERS
    )
    distance_traveled = queries.pick_representative_value(distances_by_user, leader_id)

    route_analytics = build_route_analytics(db, trip, points_by_user=points_by_user, leader_id=leader_id)

    alerts = alerts_service.list_alerts(db, trip.id, limit=10000)
    critical_alerts = sum(1 for a in alerts if a.severity.value == "CRITICAL")

    sos_events = sos_service.list_sos(db, trip.id, limit=10000)

    route_deviations = len(
        intelligence_events.list_events(db, trip.id, event_type=IntelligenceEventType.ROUTE_DEVIATION, limit=5000)
    )

    return TripAnalytics(
        trip_id=trip.id,
        status=trip.status.value,
        started_at=trip.started_at,
        ended_at=trip.ended_at,
        duration_seconds=duration_seconds,
        member_count=len(members),
        distance_traveled_meters=round(distance_traveled) if distance_traveled is not None else None,
        route_available=route_analytics.route_available,
        planned_distance_meters=route_analytics.planned_distance_meters,
        route_completion_percent=route_analytics.completion_percent,
        alerts_count=len(alerts),
        critical_alerts_count=critical_alerts,
        sos_count=len(sos_events),
        route_deviations=route_deviations,
        source=source,
    )
