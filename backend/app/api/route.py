import logging
import uuid
from typing import List, Optional

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from starlette.concurrency import run_in_threadpool

from app.core.database import get_db
from app.core.errors import AppHTTPException
from app.core.redis import get_redis
from app.dependencies.trip import require_trip_leader, require_trip_member
from app.models.enums import RouteStatus, TripStatus
from app.models.route import Route
from app.models.trip import Trip
from app.route import service as route_service
from app.schemas.route import RouteCreate, RouteMemberProgress, RouteProgressResponse, RouteResponse

logger = logging.getLogger("rally.route")

router = APIRouter(tags=["Route"])


def _serialize_route(route: Route) -> RouteResponse:
    return RouteResponse.model_validate(route)


def _get_route_or_404(db: Session, trip_id: uuid.UUID) -> Route:
    route = route_service.get_route_by_trip(db, trip_id)
    if route is None:
        raise AppHTTPException(status_code=404, code="ROUTE_NOT_FOUND", detail="This trip has no planned route.")
    return route


@router.post("/trips/{trip_id}/route", response_model=RouteResponse, status_code=201)
def create_route_endpoint(
    data: RouteCreate,
    trip: Trip = Depends(require_trip_leader),
    db: Session = Depends(get_db),
):
    """Create (or, while still PLANNED, replace) the trip's route. Only
    the group leader may do this — see require_trip_leader — and only
    while the trip itself is still CREATED (app/route/service.py enforces
    the state check)."""
    route = route_service.create_or_replace_route(db, trip, data)
    return _serialize_route(route)


@router.get("/trips/{trip_id}/route", response_model=RouteResponse)
def get_route_endpoint(
    trip: Trip = Depends(require_trip_member),
    db: Session = Depends(get_db),
):
    route = _get_route_or_404(db, trip.id)
    return _serialize_route(route)


@router.get("/trips/{trip_id}/route/progress", response_model=RouteProgressResponse)
async def get_route_progress_endpoint(
    trip: Trip = Depends(require_trip_member),
    db: Session = Depends(get_db),
):
    """Live per-member + group progress against the planned route. Only
    meaningful once both the trip and its route are ACTIVE — a route that
    hasn't started yet has no live locations to match against."""
    route = _get_route_or_404(db, trip.id)
    if trip.status != TripStatus.ACTIVE or route.status != RouteStatus.ACTIVE:
        raise AppHTTPException(
            status_code=409,
            code="ROUTE_NOT_ACTIVE",
            detail="Route progress is only available while the trip and its route are ACTIVE.",
        )

    try:
        redis = get_redis()
    except RuntimeError as exc:
        raise AppHTTPException(
            status_code=503, code="LIVE_TRACKING_UNAVAILABLE", detail="Live tracking is currently unavailable."
        ) from exc

    members, group_fraction, trip_arrived = await route_service.get_live_route_progress(db, redis, trip, route)

    member_items: List[RouteMemberProgress] = []
    leader_item: Optional[RouteMemberProgress] = None
    for m in members:
        item = RouteMemberProgress(
            user_id=uuid.UUID(m.user_id),
            name=m.name,
            role=m.role,
            route_state=m.route_state,
            route_fraction=m.match.route_fraction if m.match else None,
            distance_traveled_meters=m.match.distance_traveled_meters if m.match else None,
            distance_remaining_meters=m.match.distance_remaining_meters if m.match else None,
            distance_from_route_meters=m.match.distance_from_route_meters if m.match else None,
            eta_seconds=m.eta.eta_seconds if m.eta else None,
            eta_source=m.eta.source if m.eta else None,
            location_age_seconds=m.location_age_seconds,
            presence=m.presence,
        )
        member_items.append(item)
        if m.role == "LEADER":
            leader_item = item

    return RouteProgressResponse(
        trip_id=trip.id,
        route_id=route.id,
        group_route_fraction=group_fraction,
        trip_arrived=trip_arrived,
        leader=leader_item,
        members=member_items,
    )
