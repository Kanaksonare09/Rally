"""
Completed-trip analytics snapshots (trip_analytics_snapshots). Generated
once when a trip finishes (see app/api/trips.py::end_trip_endpoint),
purely so a completed trip's dashboard/history doesn't recompute the same
aggregation on every request. The original tables remain the source of
truth — this table is entirely derived and, in principle, disposable and
regenerable from them.

IMPORTANT: trip completion itself must never fail because analytics
generation failed — see generate_snapshot_for_completed_trip()'s caller
in app/api/trips.py, which wraps this in a try/except and only logs.
"""

import logging
import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.analytics.trip_analytics import compute_trip_analytics
from app.models.trip import Trip
from app.models.trip_analytics_snapshot import TripAnalyticsSnapshot
from app.schemas.analytics import TripAnalytics

logger = logging.getLogger("rally.analytics")


def get_snapshot(db: Session, trip_id: uuid.UUID) -> Optional[TripAnalyticsSnapshot]:
    return db.scalars(select(TripAnalyticsSnapshot).where(TripAnalyticsSnapshot.trip_id == trip_id)).first()


def generate_snapshot(db: Session, trip: Trip) -> TripAnalyticsSnapshot:
    """Idempotent: if a snapshot already exists for this trip (a retried
    end-trip call, or two concurrent requests racing), returns the
    existing row rather than creating a second one. `trip_id` is UNIQUE at
    the database level (see migration 0006) — the actual guarantee against
    two concurrent generations both winning; the upfront lookup here just
    closes the common-case window and avoids the wasted analytics
    computation on the common "already generated" path."""
    existing = get_snapshot(db, trip.id)
    if existing is not None:
        return existing

    analytics: TripAnalytics = compute_trip_analytics(db, trip, source="live")

    snapshot = TripAnalyticsSnapshot(
        trip_id=trip.id,
        duration_seconds=analytics.duration_seconds,
        distance_traveled_meters=analytics.distance_traveled_meters,
        planned_distance_meters=analytics.planned_distance_meters,
        completion_percent=analytics.route_completion_percent,
        member_count=analytics.member_count,
        alerts_count=analytics.alerts_count,
        critical_alerts_count=analytics.critical_alerts_count,
        sos_count=analytics.sos_count,
        route_deviations=analytics.route_deviations,
        generated_at=datetime.now(timezone.utc),
    )
    db.add(snapshot)
    try:
        db.commit()
    except IntegrityError:
        # Another request generated it first, in the gap between our
        # lookup above and this commit — theirs won, use it.
        db.rollback()
        return get_snapshot(db, trip.id)

    db.refresh(snapshot)
    return snapshot


def generate_snapshot_safely(db: Session, trip: Trip) -> None:
    """The only entry point app/api/trips.py should call — swallows any
    failure so a snapshot-generation bug can never block trip completion
    itself, per this module's IMPORTANT note above."""
    try:
        generate_snapshot(db, trip)
    except Exception:
        logger.exception("Failed to generate analytics snapshot for trip_id=%s", trip.id)


def snapshot_to_trip_analytics(trip: Trip, snapshot: TripAnalyticsSnapshot) -> TripAnalytics:
    """Reshapes a stored snapshot back into the same TripAnalytics
    contract compute_trip_analytics() returns live, so
    GET /trips/{trip_id}/analytics never has two different response
    shapes depending on whether it happened to be served from cache."""
    return TripAnalytics(
        trip_id=trip.id,
        status=trip.status.value,
        started_at=trip.started_at,
        ended_at=trip.ended_at,
        duration_seconds=snapshot.duration_seconds,
        member_count=snapshot.member_count,
        distance_traveled_meters=snapshot.distance_traveled_meters,
        route_available=snapshot.planned_distance_meters is not None,
        planned_distance_meters=snapshot.planned_distance_meters,
        route_completion_percent=snapshot.completion_percent,
        alerts_count=snapshot.alerts_count,
        critical_alerts_count=snapshot.critical_alerts_count,
        sos_count=snapshot.sos_count,
        route_deviations=snapshot.route_deviations,
        source="snapshot",
    )
