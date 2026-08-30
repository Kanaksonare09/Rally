"""
ETA — deterministic, not ML/AI-predicted (per this phase's explicit
scope). Two entry points:

  calculate_eta()       — one member's ETA: remaining route distance
                           divided by a representative speed, preferring
                           their own recent GPS speed when it's usable,
                           falling back to the route's declared average
                           speed, then a configured baseline.
  calculate_group_eta() — "when is the group likely to finish together,"
                           built from a representative (median) remaining
                           distance and a representative (median) speed
                           among currently-moving members — deliberately
                           NOT the fastest member's ETA, which would just
                           answer "when does the first person arrive."

Every edge case (no route, no GPS, the whole group stopped, an extreme/
implausible speed reading, distance already at zero) is handled by
falling through to a less specific speed source rather than fabricating a
number — `eta_available=False` / `eta_seconds=None` is always the answer
when NOTHING usable is left to fall back to. Never `eta_seconds=0` for
"unknown" — 0 is reserved for a genuinely zero remaining distance.
"""

from dataclasses import dataclass
from statistics import median
from typing import List, Optional, Tuple

from app.intelligence.thresholds import Thresholds


@dataclass(frozen=True)
class EtaResult:
    eta_available: bool
    eta_seconds: Optional[float]
    # "recent_speed" (this member/group's own live GPS speed) |
    # "route_estimated_duration" (route's own declared duration -> average
    # speed) | "route_baseline" (BASELINE_ROUTE_SPEED_MPS fallback) |
    # "unavailable"
    source: str


def _is_usable_speed(speed_mps: Optional[float], thresholds: Thresholds) -> bool:
    """A live speed reading is only trustworthy as an ETA driver when
    it's neither "basically stopped" (see the STOPPED-GROUP edge case —
    dividing by a near-zero speed would produce a wildly inflated ETA,
    not a genuinely large one) nor an implausible sensor glitch above
    MAX_REASONABLE_SPEED_MPS."""
    return speed_mps is not None and thresholds.stop_speed_mps < speed_mps <= thresholds.max_reasonable_speed_mps


class EtaService:
    @staticmethod
    def calculate_eta(
        *,
        distance_remaining_meters: float,
        route_distance_meters: float,
        route_estimated_duration_seconds: Optional[int],
        current_speed_mps: Optional[float],
        thresholds: Thresholds,
    ) -> EtaResult:
        remaining = max(0.0, distance_remaining_meters)
        if remaining <= 0:
            return EtaResult(eta_available=True, eta_seconds=0.0, source="route_estimated_duration")

        if _is_usable_speed(current_speed_mps, thresholds):
            return EtaResult(eta_available=True, eta_seconds=remaining / current_speed_mps, source="recent_speed")

        if route_estimated_duration_seconds and route_estimated_duration_seconds > 0 and route_distance_meters > 0:
            average_speed_mps = route_distance_meters / route_estimated_duration_seconds
            if average_speed_mps > 0:
                return EtaResult(
                    eta_available=True, eta_seconds=remaining / average_speed_mps, source="route_estimated_duration"
                )

        baseline_speed = thresholds.baseline_route_speed_mps
        if baseline_speed <= 0:
            return EtaResult(eta_available=False, eta_seconds=None, source="unavailable")
        return EtaResult(eta_available=True, eta_seconds=remaining / baseline_speed, source="route_baseline")

    @staticmethod
    def calculate_group_eta(
        *,
        members: List[Tuple[float, Optional[float]]],  # (distance_remaining_meters, current_speed_mps) per member
        route_distance_meters: float,
        route_estimated_duration_seconds: Optional[int],
        thresholds: Thresholds,
    ) -> EtaResult:
        """"When the group is likely to finish together" — built from the
        MEDIAN remaining distance across members with a usable route
        match (a straggler pulls this toward "later," which is the
        correct behavior for a group ETA) and the MEDIAN speed among
        currently-moving members only (stopped/offline members don't get
        to drag the group's representative pace to zero — they simply
        don't contribute a speed sample; see the STOPPED-GROUP edge case).
        Deliberately never the fastest member's own ETA."""
        distances = [d for d, _ in members if d is not None]
        if not distances:
            return EtaResult(eta_available=False, eta_seconds=None, source="unavailable")

        representative_remaining = max(0.0, median(distances))
        if representative_remaining <= 0:
            return EtaResult(eta_available=True, eta_seconds=0.0, source="route_estimated_duration")

        moving_speeds = [s for _, s in members if _is_usable_speed(s, thresholds)]
        if moving_speeds:
            representative_speed = median(moving_speeds)
            return EtaResult(
                eta_available=True, eta_seconds=representative_remaining / representative_speed, source="recent_speed"
            )

        # No member currently has a usable moving speed (the whole group
        # is stopped, or GPS is missing) — fall back the same way a
        # single member's ETA would.
        return EtaService.calculate_eta(
            distance_remaining_meters=representative_remaining,
            route_distance_meters=route_distance_meters,
            route_estimated_duration_seconds=route_estimated_duration_seconds,
            current_speed_mps=None,
            thresholds=thresholds,
        )
