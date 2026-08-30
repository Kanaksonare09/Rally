"""Unified chronological trip timeline — GET /trips/{trip_id}/timeline.

Combines trip lifecycle, route activation, intelligence-event, alert, and
SOS rows into one ascending-by-timestamp list. Every row from a source
table contributes at most one "created" entry and (only when it actually
happened) one "resolved" entry — genuinely two different moments, not a
duplicate of the same one.
"""

from typing import List

from sqlalchemy.orm import Session

from app.alerts import service as alerts_service
from app.analytics.safety_analytics import ANOMALY_EVENT_TYPES
from app.intelligence import events as intelligence_events
from app.models.enums import RouteStatus, TripStatus
from app.models.trip import Trip
from app.route import service as route_service
from app.schemas.analytics import TimelineEvent
from app.sos import service as sos_service


def build_timeline(db: Session, trip: Trip) -> List[TimelineEvent]:
    events: List[TimelineEvent] = []

    if trip.started_at is not None:
        events.append(TimelineEvent(type="TRIP_STARTED", timestamp=trip.started_at, data={}))

    route = route_service.get_route_by_trip(db, trip.id)
    if route is not None:
        events.append(
            TimelineEvent(
                type="ROUTE_CREATED", timestamp=route.created_at, data={"route_id": str(route.id), "name": route.name}
            )
        )
        # Route activation has no dedicated timestamp column of its own —
        # it happens synchronously with trip start (see
        # app/api/trips.py::start_trip_endpoint), so trip.started_at is
        # the accurate moment for it whenever the route did progress past
        # PLANNED.
        if route.status != RouteStatus.PLANNED and trip.started_at is not None:
            events.append(TimelineEvent(type="ROUTE_ACTIVATED", timestamp=trip.started_at, data={"route_id": str(route.id)}))

    for event in intelligence_events.list_events(db, trip.id, limit=10000):
        if event.event_type not in ANOMALY_EVENT_TYPES:
            continue
        events.append(
            TimelineEvent(
                type=event.event_type.value,
                timestamp=event.detected_at,
                data={
                    "user_id": str(event.user_id) if event.user_id else None,
                    "related_user_id": str(event.related_user_id) if event.related_user_id else None,
                    "severity": event.severity.value,
                    "metadata": event.event_metadata,
                },
            )
        )
        if event.resolved_at is not None:
            events.append(
                TimelineEvent(
                    type=f"{event.event_type.value}_RESOLVED",
                    timestamp=event.resolved_at,
                    data={"user_id": str(event.user_id) if event.user_id else None},
                )
            )

    for alert in alerts_service.list_alerts(db, trip.id, limit=10000):
        events.append(
            TimelineEvent(
                type="ALERT_CREATED",
                timestamp=alert.created_at,
                data={
                    "alert_id": str(alert.id),
                    "alert_type": alert.alert_type.value,
                    "severity": alert.severity.value,
                    "user_id": str(alert.user_id) if alert.user_id else None,
                },
            )
        )
        if alert.resolved_at is not None:
            events.append(
                TimelineEvent(type="ALERT_RESOLVED", timestamp=alert.resolved_at, data={"alert_id": str(alert.id)})
            )

    for sos in sos_service.list_sos(db, trip.id, limit=10000):
        events.append(
            TimelineEvent(
                type="SOS",
                timestamp=sos.triggered_at,
                data={"sos_id": str(sos.id), "user_id": str(sos.user_id) if sos.user_id else None},
            )
        )
        if sos.resolved_at is not None:
            events.append(TimelineEvent(type="SOS_RESOLVED", timestamp=sos.resolved_at, data={"sos_id": str(sos.id)}))

    if trip.status == TripStatus.COMPLETED and trip.ended_at is not None:
        events.append(TimelineEvent(type="TRIP_COMPLETED", timestamp=trip.ended_at, data={}))
    elif trip.status == TripStatus.CANCELLED:
        # No dedicated cancelled_at column — updated_at (TimestampMixin's
        # onupdate) is the moment trip_service.cancel_trip's status change
        # was actually committed, the closest accurate timestamp available
        # without adding a new column (see trip_service.py: cancellation
        # doesn't touch ended_at).
        events.append(TimelineEvent(type="TRIP_CANCELLED", timestamp=trip.updated_at, data={}))

    events.sort(key=lambda e: e.timestamp)
    return events
