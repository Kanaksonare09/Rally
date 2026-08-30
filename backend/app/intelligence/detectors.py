"""
The six detectors: falling behind, group separation, isolated member,
speed anomaly, unexpected stop, moving together. Each is persistence-gated
— a condition must hold continuously for its configured duration before
`detected=True` — using a small Redis timer per (trip, event_type,
subject) so a single noisy reading can never create an event (the "no
false positives" section of this phase's spec).

Every detector returns a DetectionResult per relevant subject regardless
of whether it's currently detected — app/intelligence/events.py decides
create/update/resolve from that, so a detector going from detected=True to
detected=False is exactly what resolves an active event.

Movement-state transition bookkeeping (recording STOPPED/MOVING as
lightweight timeline markers) is handled in engine.py, not here — it's a
direct side effect of app/intelligence/movement.py's classification, not
a condition that needs its own persistence-duration gate.
"""

import json
from dataclasses import dataclass
from datetime import datetime
from typing import Dict, List, Optional

from redis.asyncio import Redis

from app.core.redis_keys import intel_condition_key
from app.intelligence.group_analysis import GroupAnalysisResult
from app.intelligence.thresholds import Thresholds
from app.models.enums import IntelligenceEventType, IntelligenceSeverity

GROUP_SUBJECT = "group"


@dataclass(frozen=True)
class DetectionResult:
    event_type: IntelligenceEventType
    severity: IntelligenceSeverity
    user_id: Optional[str]
    related_user_id: Optional[str]
    detected: bool
    metadata: dict


async def _condition_elapsed_seconds(
    redis: Redis, trip_id, event_type: IntelligenceEventType, subject: str, currently_true: bool, now: datetime
) -> float:
    """How long `currently_true` has held continuously for this
    (trip, event_type, subject). The timer resets to zero — and its Redis
    key is deleted — the instant the condition goes false, so intermittent
    blips never accumulate toward the persistence threshold."""
    key = intel_condition_key(trip_id, event_type.value, subject)
    if not currently_true:
        await redis.delete(key)
        return 0.0

    raw = await redis.get(key)
    if raw is None:
        await redis.set(key, json.dumps({"since": now.isoformat()}), ex=3600)
        return 0.0

    since = datetime.fromisoformat(json.loads(raw)["since"])
    return (now - since).total_seconds()


async def detect_falling_behind(
    redis: Redis, trip_id, group: GroupAnalysisResult, thresholds: Thresholds, now: datetime
) -> List[DetectionResult]:
    results = []
    for user_id in group.eligible_member_ids:
        analysis = group.members[user_id]
        distance = analysis.distance_from_center_meters
        condition = distance is not None and distance > thresholds.falling_behind_distance_meters

        elapsed = await _condition_elapsed_seconds(
            redis, trip_id, IntelligenceEventType.FALLING_BEHIND, user_id, condition, now
        )
        detected = condition and elapsed >= thresholds.falling_behind_duration_seconds

        results.append(
            DetectionResult(
                event_type=IntelligenceEventType.FALLING_BEHIND,
                severity=IntelligenceSeverity.WARNING,
                user_id=user_id,
                related_user_id=None,
                detected=detected,
                metadata={
                    "distance_meters": round(distance, 1) if distance is not None else None,
                    "threshold_meters": thresholds.falling_behind_distance_meters,
                    "duration_seconds": round(elapsed, 1),
                }
                if condition
                else {},
            )
        )
    return results


async def detect_isolated_member(
    redis: Redis, trip_id, group: GroupAnalysisResult, thresholds: Thresholds, now: datetime
) -> List[DetectionResult]:
    results = []
    for user_id in group.eligible_member_ids:
        analysis = group.members[user_id]
        condition = analysis.is_isolated

        elapsed = await _condition_elapsed_seconds(
            redis, trip_id, IntelligenceEventType.ISOLATED_MEMBER, user_id, condition, now
        )
        detected = condition and elapsed >= thresholds.isolated_member_duration_seconds

        results.append(
            DetectionResult(
                event_type=IntelligenceEventType.ISOLATED_MEMBER,
                severity=IntelligenceSeverity.WARNING,
                user_id=user_id,
                related_user_id=analysis.nearest_other_member_id,
                detected=detected,
                metadata={
                    "nearest_member_distance_meters": (
                        round(analysis.nearest_other_member_distance_meters, 1)
                        if analysis.nearest_other_member_distance_meters is not None
                        else None
                    ),
                    "threshold_meters": thresholds.isolated_member_distance_meters,
                    "duration_seconds": round(elapsed, 1),
                }
                if condition
                else {},
            )
        )
    return results


async def detect_group_separation(
    redis: Redis, trip_id, group: GroupAnalysisResult, thresholds: Thresholds, now: datetime
) -> DetectionResult:
    condition = len(group.eligible_member_ids) >= 2 and len(group.clusters) > 1

    elapsed = await _condition_elapsed_seconds(
        redis, trip_id, IntelligenceEventType.GROUP_SEPARATION, GROUP_SUBJECT, condition, now
    )
    detected = condition and elapsed >= thresholds.group_separation_duration_seconds

    metadata = {}
    if condition:
        metadata = {
            "cluster_sizes": [len(c) for c in group.clusters],
            "main_cluster_members": group.clusters[0],
            "separated_members": [m for cluster in group.clusters[1:] for m in cluster],
            "threshold_meters": thresholds.group_separation_distance_meters,
            "duration_seconds": round(elapsed, 1),
        }

    return DetectionResult(
        event_type=IntelligenceEventType.GROUP_SEPARATION,
        severity=IntelligenceSeverity.WARNING,
        user_id=None,
        related_user_id=None,
        detected=detected,
        metadata=metadata,
    )


async def detect_speed_anomaly(
    redis: Redis,
    trip_id,
    speeds: Dict[str, Optional[float]],
    accuracies: Dict[str, Optional[float]],
    thresholds: Thresholds,
    now: datetime,
) -> List[DetectionResult]:
    """Unlike the other detectors, this doesn't run only on
    `group.eligible_member_ids` — a member can have a genuine speed
    anomaly even if their location is currently too imprecise for
    clustering purposes, as long as the *speed* reading itself is
    trustworthy (see the accuracy gate below)."""
    results = []
    for user_id, speed in speeds.items():
        accuracy = accuracies.get(user_id)
        accuracy_ok = accuracy is None or accuracy <= thresholds.min_usable_accuracy_meters
        condition = accuracy_ok and speed is not None and speed > thresholds.max_reasonable_speed_mps

        elapsed = await _condition_elapsed_seconds(
            redis, trip_id, IntelligenceEventType.SPEED_ANOMALY, user_id, condition, now
        )
        detected = condition and elapsed >= thresholds.speed_anomaly_duration_seconds

        results.append(
            DetectionResult(
                event_type=IntelligenceEventType.SPEED_ANOMALY,
                severity=IntelligenceSeverity.WARNING,
                user_id=user_id,
                related_user_id=None,
                detected=detected,
                metadata={
                    "observed_speed_mps": round(speed, 2) if speed is not None else None,
                    "threshold_mps": thresholds.max_reasonable_speed_mps,
                    "duration_seconds": round(elapsed, 1),
                }
                if condition
                else {},
            )
        )
    return results


async def detect_unexpected_stop(
    redis: Redis,
    trip_id,
    movement_states: Dict[str, str],
    thresholds: Thresholds,
    now: datetime,
) -> List[DetectionResult]:
    """A stop is "unexpected" specifically when it happens while the rest
    of the group keeps moving — everyone stopping together (a lunch break,
    a red light) is just normal STOPPED state, not a detection. That's
    what distinguishes this from the plain STOPPED movement-state marker
    recorded in engine.py."""
    stopped_members = [uid for uid, state in movement_states.items() if state == "STOPPED"]
    group_has_movement = any(state == "MOVING" for state in movement_states.values())

    results = []
    for user_id in stopped_members:
        condition = group_has_movement

        elapsed = await _condition_elapsed_seconds(
            redis, trip_id, IntelligenceEventType.UNEXPECTED_STOP, user_id, condition, now
        )
        detected = condition and elapsed >= thresholds.stop_duration_seconds

        results.append(
            DetectionResult(
                event_type=IntelligenceEventType.UNEXPECTED_STOP,
                severity=IntelligenceSeverity.WARNING,
                user_id=user_id,
                related_user_id=None,
                detected=detected,
                metadata={
                    "duration_seconds": round(elapsed, 1),
                    "stop_speed_threshold_mps": thresholds.stop_speed_mps,
                }
                if condition
                else {},
            )
        )
    return results


async def detect_route_deviation(
    redis: Redis,
    trip_id,
    distances_from_route: Dict[str, Optional[float]],
    thresholds: Thresholds,
    now: datetime,
) -> List[DetectionResult]:
    """Phase 9 — the one route-related detector that persists as a real
    intelligence_events row (see ROUTE_DEVIATION in IntelligenceEventType;
    the other route states — ON_ROUTE/OFF_ROUTE/NEAR_DESTINATION/ARRIVED
    — are ephemeral labels on a progress snapshot, not events, see
    app/route/progress.py).

    `distances_from_route` only contains members app/route/service.py
    actually matched against the route this tick (a fresh-enough, online
    live location) — a member with no usable location isn't "on route" or
    "off route," they're simply not evaluated, exactly like every other
    detector's accuracy/staleness gates above.

    Persistence-gated by ROUTE_DEVIATION_DURATION_SECONDS via the same
    condition-timer helper every other detector uses, which is also what
    keeps this resistant to flapping: the instant a member's distance
    drops back under the threshold, `condition` goes False, the timer
    resets, and the next `apply_detection()` call resolves the event."""
    results = []
    for user_id, distance in distances_from_route.items():
        condition = distance is not None and distance > thresholds.off_route_threshold_meters

        elapsed = await _condition_elapsed_seconds(
            redis, trip_id, IntelligenceEventType.ROUTE_DEVIATION, user_id, condition, now
        )
        detected = condition and elapsed >= thresholds.route_deviation_duration_seconds

        results.append(
            DetectionResult(
                event_type=IntelligenceEventType.ROUTE_DEVIATION,
                severity=IntelligenceSeverity.WARNING,
                user_id=user_id,
                related_user_id=None,
                detected=detected,
                metadata={
                    "distance_from_route_meters": round(distance, 1) if distance is not None else None,
                    "threshold_meters": thresholds.off_route_threshold_meters,
                    "duration_seconds": round(elapsed, 1),
                }
                if condition
                else {},
            )
        )
    return results


async def detect_moving_together(
    redis: Redis, trip_id, group: GroupAnalysisResult, movement_states: Dict[str, str], thresholds: Thresholds, now: datetime
) -> DetectionResult:
    """The positive counterpart to separation/isolation — useful for the
    dashboard showing "everything's fine," not just problems."""
    moving_count = sum(1 for uid in group.eligible_member_ids if movement_states.get(uid) == "MOVING")
    condition = (
        len(group.eligible_member_ids) >= 2
        and group.is_cohesive
        and len(group.clusters) <= 1
        and moving_count >= 2
    )

    # No extra persistence duration here — event-level dedup (events.py)
    # already prevents a new row per tick; a debounce timer would only
    # delay the "everything's fine" signal without meaningfully reducing
    # noise the way it matters for warning-level detectors.
    return DetectionResult(
        event_type=IntelligenceEventType.MOVING_TOGETHER,
        severity=IntelligenceSeverity.INFO,
        user_id=None,
        related_user_id=None,
        detected=condition,
        metadata={
            "member_count": len(group.eligible_member_ids),
            "max_pairwise_distance_meters": round(group.max_pairwise_distance_meters, 1),
            "cohesion_threshold_meters": thresholds.group_cohesion_distance_meters,
        }
        if condition
        else {},
    )
