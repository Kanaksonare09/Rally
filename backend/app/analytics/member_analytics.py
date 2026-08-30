"""Per-member trip statistics — see GET /trips/{trip_id}/analytics/members."""

import uuid
from datetime import datetime, timezone
from typing import Dict, List

from sqlalchemy.orm import Session

from app.alerts import service as alerts_service
from app.analytics import queries
from app.analytics.route_analytics import compute_route_completion
from app.core.config import settings
from app.intelligence import events as intelligence_events
from app.models.enums import IntelligenceEventType, TripStatus
from app.models.trip import Trip
from app.route import service as route_service
from app.schemas.analytics import MemberAnalyticsItem, MemberAnalyticsResponse
from app.sos import service as sos_service


def build_member_analytics(db: Session, trip: Trip) -> MemberAnalyticsResponse:
    members = queries.list_active_group_members(db, trip.group_id)
    points_by_user = queries.fetch_location_points(db, trip.id)
    movement_by_user = queries.fetch_movement_intervals_by_user(db, trip.id)

    route = route_service.get_route_by_trip(db, trip.id)
    leader_id = queries.get_group_leader_id(db, trip.group_id)

    deviation_events = intelligence_events.list_events(
        db, trip.id, event_type=IntelligenceEventType.ROUTE_DEVIATION, limit=5000
    )
    deviations_by_user: Dict[str, int] = {}
    for event in deviation_events:
        if event.user_id:
            deviations_by_user[str(event.user_id)] = deviations_by_user.get(str(event.user_id), 0) + 1

    alerts = alerts_service.list_alerts(db, trip.id, limit=10000)
    alerts_by_user: Dict[str, int] = {}
    for alert in alerts:
        if alert.user_id:
            alerts_by_user[str(alert.user_id)] = alerts_by_user.get(str(alert.user_id), 0) + 1

    sos_events = sos_service.list_sos(db, trip.id, limit=10000)
    sos_by_user: Dict[str, int] = {}
    for sos in sos_events:
        if sos.user_id:
            sos_by_user[str(sos.user_id)] = sos_by_user.get(str(sos.user_id), 0) + 1

    trip_end = trip.ended_at if trip.status != TripStatus.ACTIVE and trip.ended_at else datetime.now(timezone.utc)

    items: List[MemberAnalyticsItem] = []
    for member in members:
        uid_str = str(member["user_id"])
        points = points_by_user.get(uid_str, [])

        distance = queries.compute_member_distance_meters(
            points, max_speed_mps=settings.MAX_ANALYTICS_SPEED_MPS, max_accuracy_meters=settings.MIN_USABLE_ACCURACY_METERS
        )
        active_duration = queries.compute_active_duration_seconds(points)

        available, moving_seconds, stopped_seconds = queries.compute_movement_durations(
            movement_by_user.get(uid_str, []), trip_end=trip_end
        )

        route_completion_percent = None
        if route is not None and points:
            completion_percent, _remaining, _arrived = compute_route_completion(
                route, {uid_str: points}, leader_id=None  # single-member lookup: no leader fallback needed
            )
            route_completion_percent = completion_percent

        items.append(
            MemberAnalyticsItem(
                user_id=member["user_id"],
                name=member["name"],
                role=member["role"],
                joined_at=member["joined_at"],
                distance_traveled_meters=round(distance) if distance is not None else None,
                active_duration_seconds=active_duration,
                movement_duration_available=available,
                moving_duration_seconds=moving_seconds,
                stopped_duration_seconds=stopped_seconds,
                route_completion_percent=route_completion_percent,
                route_deviations=deviations_by_user.get(uid_str, 0),
                alerts_received=alerts_by_user.get(uid_str, 0),
                sos_triggered=sos_by_user.get(uid_str, 0),
            )
        )

    return MemberAnalyticsResponse(trip_id=trip.id, members=items)
