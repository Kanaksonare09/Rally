import logging
import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.analytics import insights as insights_module
from app.analytics import member_analytics, replay as replay_module, safety_analytics, timeline as timeline_module
from app.analytics import route_analytics as route_analytics_module
from app.analytics import trip_analytics as trip_analytics_module
from app.analytics.dashboard import build_dashboard
from app.analytics.snapshot import get_snapshot, snapshot_to_trip_analytics
from app.core.config import settings
from app.core.database import get_db
from app.core.redis import get_redis
from app.dependencies.auth import get_current_user_id
from app.dependencies.trip import require_trip_member
from app.models.enums import TripStatus
from app.models.trip import Trip
from app.risk.service import calculate_trip_risk
from app.schemas.analytics import (
    DashboardResponse,
    MemberAnalyticsResponse,
    RouteAnalytics,
    SafetyAnalytics,
    TripAnalytics,
    TripInsights,
    TripReplay,
    TripTimeline,
)
from app.schemas.risk import RiskScore

logger = logging.getLogger("rally.analytics")

router = APIRouter(tags=["Analytics"])


@router.get("/trips/{trip_id}/analytics", response_model=TripAnalytics)
def get_trip_analytics_endpoint(
    trip: Trip = Depends(require_trip_member),
    db: Session = Depends(get_db),
):
    """Trip-level headline analytics — active trip membership required.
    For a COMPLETED trip, serves the immutable snapshot
    (trip_analytics_snapshots) when one exists instead of recomputing;
    every other status is always computed fresh."""
    if trip.status == TripStatus.COMPLETED:
        snapshot = get_snapshot(db, trip.id)
        if snapshot is not None:
            return snapshot_to_trip_analytics(trip, snapshot)

    return trip_analytics_module.compute_trip_analytics(db, trip, source="live")


@router.get("/trips/{trip_id}/analytics/members", response_model=MemberAnalyticsResponse)
def get_member_analytics_endpoint(
    trip: Trip = Depends(require_trip_member),
    db: Session = Depends(get_db),
):
    return member_analytics.build_member_analytics(db, trip)


@router.get("/trips/{trip_id}/analytics/route", response_model=RouteAnalytics)
def get_route_analytics_endpoint(
    trip: Trip = Depends(require_trip_member),
    db: Session = Depends(get_db),
):
    return route_analytics_module.build_route_analytics(db, trip)


@router.get("/trips/{trip_id}/analytics/safety", response_model=SafetyAnalytics)
def get_safety_analytics_endpoint(
    trip: Trip = Depends(require_trip_member),
    db: Session = Depends(get_db),
):
    return safety_analytics.build_safety_analytics(db, trip)


@router.get("/trips/{trip_id}/timeline", response_model=TripTimeline)
def get_trip_timeline_endpoint(
    trip: Trip = Depends(require_trip_member),
    db: Session = Depends(get_db),
):
    events = timeline_module.build_timeline(db, trip)
    return TripTimeline(trip_id=trip.id, events=events)


@router.get("/trips/{trip_id}/replay", response_model=TripReplay)
def get_trip_replay_endpoint(
    trip: Trip = Depends(require_trip_member),
    db: Session = Depends(get_db),
    interval_seconds: int = Query(
        settings.REPLAY_DEFAULT_INTERVAL_SECONDS,
        ge=settings.REPLAY_MIN_INTERVAL_SECONDS,
        le=settings.REPLAY_MAX_INTERVAL_SECONDS,
        description="Sampling resolution — larger values produce fewer, coarser frames.",
    ),
):
    """A compact, evenly-sampled replay of the trip's GPS + event history
    — never every raw point (see app/analytics/replay.py). Works for any
    trip status; a trip still ACTIVE just replays what's happened so far."""
    return replay_module.build_replay(db, trip, interval_seconds=interval_seconds)


@router.get("/trips/{trip_id}/risk", response_model=RiskScore)
def get_trip_risk_endpoint(
    trip: Trip = Depends(require_trip_member),
    db: Session = Depends(get_db),
):
    return calculate_trip_risk(db, trip)


@router.get("/trips/{trip_id}/insights", response_model=TripInsights)
def get_trip_insights_endpoint(
    trip: Trip = Depends(require_trip_member),
    db: Session = Depends(get_db),
):
    return insights_module.build_trip_insights(db, trip)


@router.get("/trips/{trip_id}/dashboard", response_model=DashboardResponse)
async def get_trip_dashboard_endpoint(
    trip: Trip = Depends(require_trip_member),
    db: Session = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    """The primary frontend dashboard endpoint. ACTIVE trips combine Redis
    live state with PostgreSQL; every other status is PostgreSQL-only —
    Redis is never required to view a completed trip's dashboard. If
    Redis is configured but unreachable during an ACTIVE trip, this
    degrades gracefully (live-only fields become null) rather than
    failing the whole request. `user_id` (the verified caller, never a
    query/body parameter) scopes the `notifications` section to the
    viewer's own unread count — never another member's."""
    redis = None
    if trip.status == TripStatus.ACTIVE:
        try:
            redis = get_redis()
        except RuntimeError:
            logger.warning("Redis not configured; serving a degraded live dashboard for trip %s.", trip.id)

    return await build_dashboard(db, redis, trip, uuid.UUID(user_id))
