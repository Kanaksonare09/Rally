"""
Orchestration. This is the one file in app/intelligence/ allowed to know
about WebSockets (app.websocket.manager/schemas) — movement.py,
distance.py, group_analysis.py, detectors.py, and events.py have no idea
WebSockets exist, per this phase's "keep the intelligence engine
independent from WebSocket code" instruction. It's also the only file that
touches the database directly (via run_in_threadpool) and Redis.

Two entry points:
  compute_current_state()   — read-only, cheap, used by BOTH the periodic
                               worker and GET /trips/{id}/intelligence.
                               Touches only Redis + one indexed membership
                               query, never location_history.
  evaluate_and_persist_trip() — the periodic worker's per-trip tick: calls
                               compute_current_state(), then persists any
                               detector transitions as intelligence_events
                               and publishes them over the trip's
                               WebSocket channel.
"""

import json
import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple

from redis.asyncio import Redis
from sqlalchemy import select
from sqlalchemy.orm import Session
from starlette.concurrency import run_in_threadpool

from app.alerts import service as alerts_service
from app.core.redis_keys import intel_eval_lock_key, intel_movement_state_key
from app.intelligence import detectors, events
from app.intelligence.detectors import DetectionResult
from app.intelligence.group_analysis import GroupAnalysisResult, MemberPosition, analyze_group
from app.intelligence.movement import MovementResult, classify_movement_state
from app.intelligence.thresholds import Thresholds, current_thresholds
from app.models.enums import IntelligenceEventType, IntelligenceSeverity, MemberStatus, RouteStatus
from app.models.group_member import GroupMember
from app.models.profile import Profile
from app.route import service as route_service
from app.services import live_state_service, presence_service
from app.websocket.manager import publish_event
from app.websocket.schemas import build_intelligence_event, build_route_deviation, build_route_progress

logger = logging.getLogger("rally.intelligence")

_EVAL_LOCK_TTL_MS = 30_000  # generous vs. the default 3s interval — see run_intelligence_worker


@dataclass
class ComputedMember:
    user_id: str
    name: Optional[str]
    role: str
    movement_state: str
    presence: str
    location_age_seconds: Optional[float]
    latitude: Optional[float]
    longitude: Optional[float]
    speed: Optional[float]
    accuracy: Optional[float]
    distance_from_group_center_meters: Optional[float]
    is_isolated: bool
    is_falling_behind: bool


@dataclass
class ComputedState:
    trip_id: uuid.UUID
    group_id: uuid.UUID
    group_state: str
    members: List[ComputedMember]
    group_analysis: GroupAnalysisResult
    # Every detector's result this tick (group-level ones included, with
    # user_id=None) — evaluate_and_persist_trip() persists from this list
    # rather than re-running every detector a second time.
    detection_results: List[DetectionResult] = field(default_factory=list)
    # (user_id, MovementResult, previous_state) — used only by
    # evaluate_and_persist_trip() to record STOPPED/MOVING transitions.
    movement_transitions: List[Tuple[str, MovementResult, Optional[str]]] = field(default_factory=list)


def _load_active_members_sync(db: Session, group_id: uuid.UUID) -> List[dict]:
    """Sync DB work — always call through run_in_threadpool. Same query
    shape as app/websocket/handlers.py's _load_active_members (kept
    separate rather than shared, since this module must not import from
    the websocket package — see the module docstring)."""
    rows = db.execute(
        select(GroupMember, Profile)
        .join(Profile, GroupMember.user_id == Profile.id)
        .where(GroupMember.group_id == group_id, GroupMember.status == MemberStatus.ACTIVE)
    ).all()
    return [
        {"user_id": member.user_id, "name": profile.full_name, "role": member.role.value}
        for member, profile in rows
    ]


async def _classify_all_members(
    redis: Redis,
    trip_id: uuid.UUID,
    members: List[dict],
    live_locations: Dict[str, dict],
    online_status: Dict[str, bool],
    thresholds: Thresholds,
    now: datetime,
) -> Dict[str, Tuple[MovementResult, Optional[str]]]:
    """Returns {user_id_str: (MovementResult, previous_state)}. Reads each
    member's debounce state from Redis, classifies, then writes the new
    state back — one round trip per member, all in-memory math otherwise."""
    results: Dict[str, Tuple[MovementResult, Optional[str]]] = {}

    for member in members:
        uid_str = str(member["user_id"])
        location = live_locations.get(uid_str)

        location_age_seconds: Optional[float] = None
        speed: Optional[float] = None
        if location is not None:
            recorded_at = datetime.fromisoformat(location["recorded_at"])
            location_age_seconds = (now - recorded_at).total_seconds()
            speed = location.get("speed")

        state_key = intel_movement_state_key(trip_id, uid_str)
        raw_prev = await redis.get(state_key)
        previous_state: Optional[str] = None
        pending_since: Optional[datetime] = None
        if raw_prev:
            parsed = json.loads(raw_prev)
            previous_state = parsed.get("state")
            if parsed.get("pending_since"):
                pending_since = datetime.fromisoformat(parsed["pending_since"])

        result = classify_movement_state(
            speed_mps=speed,
            location_age_seconds=location_age_seconds,
            presence_online=online_status.get(uid_str, False),
            previous_state=previous_state,
            pending_since=pending_since,
            now=now,
            stop_speed_mps=thresholds.stop_speed_mps,
            stop_duration_seconds=thresholds.stop_duration_seconds,
            stale_location_seconds=thresholds.stale_location_seconds,
        )

        await redis.set(
            state_key,
            json.dumps(
                {
                    "state": result.state,
                    "pending_since": result.pending_since.isoformat() if result.pending_since else None,
                }
            ),
            ex=3600,
        )
        results[uid_str] = (result, previous_state)

    return results


async def compute_current_state(db: Session, redis: Redis, trip_id: uuid.UUID, group_id: uuid.UUID) -> ComputedState:
    """Read-only (aside from the movement/condition debounce timers all
    detectors maintain regardless of caller — see detectors.py's
    docstring on why that's safe to call from a read path). Never queries
    location_history."""
    now = datetime.now(timezone.utc)
    thresholds = current_thresholds()

    members = await run_in_threadpool(_load_active_members_sync, db, group_id)
    user_ids = [m["user_id"] for m in members]

    live_locations = await live_state_service.get_live_locations(redis, trip_id, user_ids)
    online_status = await presence_service.get_online_status(redis, trip_id, user_ids)

    movement_results = await _classify_all_members(
        redis, trip_id, members, live_locations, online_status, thresholds, now
    )

    positions: List[MemberPosition] = []
    for member in members:
        uid_str = str(member["user_id"])
        location = live_locations.get(uid_str)
        movement_result, _ = movement_results[uid_str]
        if location is not None:
            positions.append(
                MemberPosition(
                    user_id=uid_str,
                    latitude=location["latitude"],
                    longitude=location["longitude"],
                    accuracy=location.get("accuracy"),
                    movement_state=movement_result.state,
                )
            )

    group = analyze_group(
        positions,
        min_accuracy_meters=thresholds.min_usable_accuracy_meters,
        isolated_distance_meters=thresholds.isolated_member_distance_meters,
        separation_distance_meters=thresholds.group_separation_distance_meters,
        cohesion_distance_meters=thresholds.group_cohesion_distance_meters,
    )

    movement_states = {uid: res.state for uid, (res, _) in movement_results.items()}
    speeds = {uid: live_locations.get(uid, {}).get("speed") for uid in movement_states}
    accuracies = {uid: live_locations.get(uid, {}).get("accuracy") for uid in movement_states}

    detection_results: List[DetectionResult] = []
    detection_results.extend(await detectors.detect_falling_behind(redis, trip_id, group, thresholds, now))
    detection_results.extend(await detectors.detect_isolated_member(redis, trip_id, group, thresholds, now))
    detection_results.extend(
        await detectors.detect_speed_anomaly(redis, trip_id, speeds, accuracies, thresholds, now)
    )
    detection_results.extend(
        await detectors.detect_unexpected_stop(redis, trip_id, movement_states, thresholds, now)
    )
    separation_result = await detectors.detect_group_separation(redis, trip_id, group, thresholds, now)
    moving_together_result = await detectors.detect_moving_together(
        redis, trip_id, group, movement_states, thresholds, now
    )
    detection_results.append(separation_result)
    detection_results.append(moving_together_result)

    falling_behind_by_user = {
        r.user_id: r.detected for r in detection_results if r.event_type == IntelligenceEventType.FALLING_BEHIND
    }
    isolated_by_user = {
        r.user_id: r.detected for r in detection_results if r.event_type == IntelligenceEventType.ISOLATED_MEMBER
    }

    if separation_result.detected:
        group_state = "SEPARATED"
    elif len(group.eligible_member_ids) < 2:
        group_state = "INSUFFICIENT_DATA"
    elif moving_together_result.detected:
        group_state = "MOVING_TOGETHER"
    elif group.is_cohesive:
        group_state = "STATIONARY"
    else:
        group_state = "SPREAD_OUT"

    computed_members: List[ComputedMember] = []
    for member in members:
        uid_str = str(member["user_id"])
        location = live_locations.get(uid_str)
        movement_result, previous_state = movement_results[uid_str]
        analysis = group.members.get(uid_str)

        computed_members.append(
            ComputedMember(
                user_id=uid_str,
                name=member["name"],
                role=member["role"],
                movement_state=movement_result.state,
                presence="ONLINE" if online_status.get(uid_str) else "OFFLINE",
                location_age_seconds=(
                    round((now - datetime.fromisoformat(location["recorded_at"])).total_seconds(), 1)
                    if location
                    else None
                ),
                latitude=location["latitude"] if location else None,
                longitude=location["longitude"] if location else None,
                speed=location.get("speed") if location else None,
                accuracy=location.get("accuracy") if location else None,
                distance_from_group_center_meters=(
                    round(analysis.distance_from_center_meters, 1)
                    if analysis and analysis.distance_from_center_meters is not None
                    else None
                ),
                is_isolated=isolated_by_user.get(uid_str, False),
                is_falling_behind=falling_behind_by_user.get(uid_str, False),
            )
        )

    movement_transitions = [
        (uid, result, previous_state)
        for uid, (result, previous_state) in movement_results.items()
        if result.state != previous_state
    ]

    return ComputedState(
        trip_id=trip_id,
        group_id=group_id,
        group_state=group_state,
        members=computed_members,
        group_analysis=group,
        detection_results=detection_results,
        movement_transitions=movement_transitions,
    )


async def _publish_intelligence_event(redis: Redis, trip_id: uuid.UUID, event, action: str) -> None:
    if event is None or action not in ("created", "resolved"):
        return
    message = build_intelligence_event(
        event_type=event.event_type.value,
        severity=event.severity.value,
        user_id=event.user_id,
        related_user_id=event.related_user_id,
        detected_at=event.detected_at.isoformat(),
        resolved_at=event.resolved_at.isoformat() if event.resolved_at else None,
        metadata=event.event_metadata,
    )
    await publish_event(redis, str(trip_id), message)


async def _apply_movement_transitions(
    db: Session, redis: Redis, trip_id: uuid.UUID, group_id: uuid.UUID, computed: ComputedState
) -> None:
    """Records plain STOPPED/MOVING markers (INFO severity) as a
    lightweight side effect of the movement classifier — not gated by its
    own persistence-duration timer, since movement.py's own hysteresis
    already prevents rapid MOVING/STOPPED/MOVING flapping from reaching
    this point at all."""
    for uid_str, result, previous_state in computed.movement_transitions:
        if previous_state in ("MOVING", "STOPPED"):
            prev_type = IntelligenceEventType.MOVING if previous_state == "MOVING" else IntelligenceEventType.STOPPED
            resolve_result = DetectionResult(
                event_type=prev_type, severity=IntelligenceSeverity.INFO, user_id=uid_str,
                related_user_id=None, detected=False, metadata={},
            )
            event, action = await events.apply_detection(db, redis, trip_id, group_id, resolve_result)
            await _publish_intelligence_event(redis, trip_id, event, action)

        if result.state in ("MOVING", "STOPPED"):
            new_type = IntelligenceEventType.MOVING if result.state == "MOVING" else IntelligenceEventType.STOPPED
            create_result = DetectionResult(
                event_type=new_type, severity=IntelligenceSeverity.INFO, user_id=uid_str,
                related_user_id=None, detected=True, metadata={"previous_state": previous_state},
            )
            event, action = await events.apply_detection(db, redis, trip_id, group_id, create_result)
            await _publish_intelligence_event(redis, trip_id, event, action)


async def _evaluate_route(db: Session, redis: Redis, trip_id: uuid.UUID, group_id: uuid.UUID, now: datetime) -> None:
    """Phase 9 — route intelligence, layered on top of everything above
    without changing it: a trip with no route, or a route not yet ACTIVE,
    makes this an immediate no-op, so every trip evaluated before this
    phase existed keeps behaving exactly as it did (falling behind, group
    separation, isolated member, unexpected stop, speed anomaly, moving
    together are computed above this call and are entirely unaffected by
    it either way).

    Deliberately re-fetches members/live-locations/presence rather than
    reusing compute_current_state()'s — same "kept separate rather than
    shared" independence this file already applies to
    app/websocket/handlers.py's own copy of _load_active_members_sync;
    app/route/service.py must not depend on this module's internals."""
    route = await run_in_threadpool(route_service.get_route_by_trip, db, trip_id)
    if route is None or route.status != RouteStatus.ACTIVE:
        return

    thresholds = current_thresholds()
    members = await run_in_threadpool(_load_active_members_sync, db, group_id)
    user_ids = [m["user_id"] for m in members]
    live_locations = await live_state_service.get_live_locations(redis, trip_id, user_ids)
    online_status = await presence_service.get_online_status(redis, trip_id, user_ids)

    member_results, group_fraction, trip_arrived = await route_service.compute_route_progress(
        redis, trip_id, route, members, live_locations, online_status, now
    )

    distances_from_route = {
        m.user_id: (m.match.distance_from_route_meters if m.match else None) for m in member_results
    }
    deviation_results = await detectors.detect_route_deviation(redis, trip_id, distances_from_route, thresholds, now)

    for result in deviation_results:
        loc = live_locations.get(result.user_id)
        latitude = loc["latitude"] if loc else None
        longitude = loc["longitude"] if loc else None

        event, action = await events.apply_detection(
            db, redis, trip_id, group_id, result, latitude=latitude, longitude=longitude
        )
        if action in ("created", "resolved"):
            logger.info(
                "intelligence event %s: trip_id=%s event_type=ROUTE_DEVIATION user_id=%s",
                action, trip_id, result.user_id,
            )
        await _publish_intelligence_event(redis, trip_id, event, action)
        # Same Phase 7 -> Phase 8 seam every other detector uses: ROUTE_
        # DEVIATION maps to a WARNING alert via the existing alert policy
        # table (app/alerts/policies.py) — no separate alert path for
        # route events.
        await alerts_service.apply_intelligence_event(db, redis, event, action)

        if action in ("created", "resolved") and event is not None:
            await publish_event(
                redis,
                str(trip_id),
                build_route_deviation(
                    user_id=event.user_id,
                    distance_from_route_meters=(event.event_metadata or {}).get("distance_from_route_meters"),
                    status="DEVIATED" if action == "created" else "BACK_ON_ROUTE",
                    detected_at=event.detected_at.isoformat(),
                ),
            )

    # A continuous live readout, not a discrete event — published every
    # tick regardless of whether anything changed, unlike
    # intelligence_event/alert/route_deviation above.
    await publish_event(
        redis,
        str(trip_id),
        build_route_progress(
            trip_id=trip_id,
            route_id=route.id,
            group_route_fraction=group_fraction,
            trip_arrived=trip_arrived,
            members=[
                {
                    "user_id": m.user_id,
                    "route_state": m.route_state,
                    "route_fraction": m.match.route_fraction if m.match else None,
                    "distance_remaining_meters": m.match.distance_remaining_meters if m.match else None,
                    "eta_seconds": m.eta.eta_seconds if m.eta else None,
                }
                for m in member_results
            ],
        ),
    )


async def evaluate_and_persist_trip(db: Session, redis: Redis, trip_id: uuid.UUID, group_id: uuid.UUID) -> Optional[ComputedState]:
    """One evaluation tick for one trip: acquire the per-trip lock (skip
    if another worker already holds it — see the module docstring on
    concurrency), compute current state, persist any detector
    transitions, publish WebSocket frames for the ones that actually
    changed (never for an unchanged "still active"/"still absent" tick)."""
    lock_key = intel_eval_lock_key(trip_id)
    acquired = await redis.set(lock_key, "1", nx=True, px=_EVAL_LOCK_TTL_MS)
    if not acquired:
        return None

    try:
        computed = await compute_current_state(db, redis, trip_id, group_id)

        for result in computed.detection_results:
            latitude = longitude = None
            if result.user_id:
                member = next((m for m in computed.members if m.user_id == result.user_id), None)
                if member:
                    latitude, longitude = member.latitude, member.longitude

            event, action = await events.apply_detection(
                db, redis, trip_id, group_id, result, latitude=latitude, longitude=longitude
            )
            if action in ("created", "resolved"):
                logger.info(
                    "intelligence event %s: trip_id=%s event_type=%s user_id=%s",
                    action, trip_id, result.event_type.value, result.user_id,
                )
            await _publish_intelligence_event(redis, trip_id, event, action)
            # The one call connecting Phase 7 to Phase 8: detectors never
            # know alerts exist (see this file's docstring), but engine.py
            # — already the seam that knows about WebSockets — is exactly
            # where "an intelligence event just changed" becomes "maybe
            # tell the Alert Engine about it." apply_intelligence_event()
            # itself decides (via app/alerts/policies.py) whether this
            # particular event_type/action actually produces anything.
            await alerts_service.apply_intelligence_event(db, redis, event, action)

        await _apply_movement_transitions(db, redis, trip_id, group_id, computed)

        try:
            await _evaluate_route(db, redis, trip_id, group_id, datetime.now(timezone.utc))
        except Exception:
            # Route intelligence must never take down group-relationship
            # evaluation above it — this whole tick's falling-behind/
            # separation/isolation/speed/stop results are already computed
            # and persisted by this point regardless of what happens here.
            logger.exception("Route evaluation failed for trip_id=%s", trip_id)

        return computed
    finally:
        # Release promptly rather than waiting out the TTL, so the next
        # tick (INTELLIGENCE_EVALUATION_INTERVAL_SECONDS later) isn't
        # blocked by a lock this same evaluation no longer needs.
        try:
            await redis.delete(lock_key)
        except Exception:
            pass
