import logging
import uuid
from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session
from starlette.concurrency import run_in_threadpool

from app.analytics import history as trip_history
from app.analytics.snapshot import generate_snapshot_safely
from app.core.database import get_db
from app.core.redis import get_redis
from app.dependencies.auth import get_current_user_id
from app.dependencies.group import require_group_member
from app.dependencies.trip import require_trip_creator_or_leader, require_trip_member
from app.models.enums import TripStatus
from app.models.group_member import GroupMember
from app.models.trip import Trip
from app.notifications import service as notification_service
from app.route import service as route_service
from app.schemas.analytics import DEFAULT_HISTORY_LIMIT, MAX_HISTORY_LIMIT, TripHistoryResponse
from app.schemas.trip import TripCreate, TripResponse, TripStart
from app.services import live_state_service, trip_service
from app.websocket.manager import publish_event
from app.websocket.schemas import build_trip_ended

logger = logging.getLogger("rally.trips")

router = APIRouter(tags=["Trips"])


@router.post("/groups/{group_id}/trips", response_model=TripResponse, status_code=status.HTTP_201_CREATED)
def create_trip_endpoint(
    group_id: uuid.UUID,
    data: TripCreate,
    user_id: str = Depends(get_current_user_id),
    member: GroupMember = Depends(require_group_member),
    db: Session = Depends(get_db),
):
    """Create a trip in CREATED state. Any active group member may do this."""
    return trip_service.create_trip(db, group_id, uuid.UUID(user_id), data)


@router.get("/groups/{group_id}/trips", response_model=TripHistoryResponse)
def list_group_trips_endpoint(
    group_id: uuid.UUID,
    member: GroupMember = Depends(require_group_member),
    db: Session = Depends(get_db),
    status_: Optional[TripStatus] = Query(None, alias="status"),
    from_: Optional[datetime] = Query(None, alias="from"),
    to: Optional[datetime] = Query(None),
    limit: int = Query(DEFAULT_HISTORY_LIMIT, ge=1, le=MAX_HISTORY_LIMIT),
    offset: int = Query(0, ge=0),
):
    """The group's trip history, newest first — paginated and filterable
    (Phase 10). Must be an active member; never exposes another group's
    trips (group_id is scoped by require_group_member, not the query)."""
    return trip_history.list_group_trip_history(
        db, group_id, status=status_, from_time=from_, to_time=to, limit=limit, offset=offset
    )


@router.get("/users/me/trips", response_model=TripHistoryResponse)
def list_my_trip_history_endpoint(
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
    status_: Optional[TripStatus] = Query(None, alias="status"),
    from_: Optional[datetime] = Query(None, alias="from"),
    to: Optional[datetime] = Query(None),
    limit: int = Query(DEFAULT_HISTORY_LIMIT, ge=1, le=MAX_HISTORY_LIMIT),
    offset: int = Query(0, ge=0),
):
    """Trips across every group the authenticated user actively belongs
    to, newest first. The user id always comes from the verified token —
    there is no user_id query/body parameter to spoof another user's
    history with."""
    return trip_history.list_user_trip_history(
        db, uuid.UUID(user_id), status=status_, from_time=from_, to_time=to, limit=limit, offset=offset
    )


@router.get("/trips/{trip_id}", response_model=TripResponse)
def get_trip_endpoint(trip: Trip = Depends(require_trip_member)):
    return trip


@router.post("/trips/{trip_id}/start", response_model=TripResponse)
def start_trip_endpoint(
    data: Optional[TripStart] = None,
    trip: Trip = Depends(require_trip_member),
    db: Session = Depends(get_db),
):
    """CREATED -> ACTIVE. Rejected with 409 if the group already has
    another active trip, or if this trip isn't CREATED. If this trip has
    a PLANNED route, it's activated (PLANNED -> ACTIVE) alongside it — a
    trip with no route is entirely unaffected (activate_route_sync is a
    no-op when there's nothing to activate)."""
    updated = trip_service.start_trip(db, trip, data)
    route_service.activate_route_sync(db, updated.id)
    notification_service.notify_group_safely(
        db, group_id=updated.group_id, type="TRIP_STARTED", title="Trip started",
        message=f"{updated.destination_name or 'A trip'} has started.", severity="INFO", trip_id=updated.id,
        dedup_key_fn=lambda uid: f"trip_started:{updated.id}:{uid}",
    )
    return updated


@router.post("/trips/{trip_id}/end", response_model=TripResponse)
async def end_trip_endpoint(
    trip: Trip = Depends(require_trip_member),
    db: Session = Depends(get_db),
):
    """ACTIVE -> COMPLETED. Also tells any live WebSocket connections for
    this trip (on every instance) that tracking has stopped, completes the
    trip's route (ACTIVE -> COMPLETED) if it has one, and generates the
    trip's analytics snapshot (Phase 10 — see app/analytics/snapshot.py).
    Snapshot generation can never fail trip completion itself: any error
    generating it is logged and swallowed, never raised here."""
    updated = await run_in_threadpool(trip_service.end_trip, db, trip)
    await run_in_threadpool(route_service.complete_route_sync, db, updated.id)
    await run_in_threadpool(generate_snapshot_safely, db, updated)
    await run_in_threadpool(
        notification_service.notify_group_safely,
        db, group_id=updated.group_id, type="TRIP_COMPLETED", title="Trip completed",
        message=f"{updated.destination_name or 'The trip'} has been completed.", severity="INFO", trip_id=updated.id,
        dedup_key_fn=lambda uid: f"trip_completed:{updated.id}:{uid}",
    )
    await _stop_live_tracking(updated)
    return updated


@router.post("/trips/{trip_id}/cancel", response_model=TripResponse)
async def cancel_trip_endpoint(
    trip: Trip = Depends(require_trip_creator_or_leader),
    db: Session = Depends(get_db),
):
    """CREATED -> CANCELLED. Only the trip's creator or the group leader.
    A CREATED trip has no live WebSocket connections yet (they require an
    ACTIVE trip to connect at all), but the Redis cleanup call is cheap
    and harmless either way, so it runs unconditionally for consistency.
    Also cancels the trip's route (PLANNED -> CANCELLED) if it has one —
    a trip can only be cancelled while still CREATED, so its route, if
    any, is necessarily still PLANNED too."""
    updated = await run_in_threadpool(trip_service.cancel_trip, db, trip)
    await run_in_threadpool(route_service.cancel_route_sync, db, updated.id)
    await _stop_live_tracking(updated)
    return updated


async def _stop_live_tracking(trip: Trip) -> None:
    """Publishes trip_ended (every instance with local connections for
    this trip closes them — see app/websocket/manager.py's subscriber
    loop) and clears the trip's temporary Redis state. Never touches
    location_history — that stays exactly as it is, permanently."""
    try:
        redis = get_redis()
    except RuntimeError:
        logger.warning("Redis not configured; skipping live-tracking shutdown for trip %s.", trip.id)
        return

    trip_id_str = str(trip.id)
    try:
        await publish_event(redis, trip_id_str, build_trip_ended(trip.id, trip.status.value))
        active_user_ids = await run_in_threadpool(_active_group_user_ids, trip.group_id)
        await live_state_service.clear_trip_state(redis, trip.id, active_user_ids)
    except Exception:
        logger.exception("Failed to stop live tracking for trip %s", trip.id)


def _active_group_user_ids(group_id: uuid.UUID) -> List[uuid.UUID]:
    from sqlalchemy import select

    from app.core.database import SessionLocal
    from app.models.enums import MemberStatus

    if SessionLocal is None:
        return []
    db = SessionLocal()
    try:
        return list(
            db.scalars(
                select(GroupMember.user_id).where(
                    GroupMember.group_id == group_id, GroupMember.status == MemberStatus.ACTIVE
                )
            ).all()
        )
    finally:
        db.close()
