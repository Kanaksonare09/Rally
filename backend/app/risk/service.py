"""
RiskService: a deterministic, explainable safety score for a trip — GET
/trips/{trip_id}/risk. Deliberately DB-only (never Redis) so the same
score is computable, the same way, for both an ACTIVE and a COMPLETED
trip — same "historical dashboard never needs Redis" principle the rest
of app/analytics/ follows. `online_count`/`member_count` are the one
optional exception: when the caller (the live dashboard) has them from
Redis, the LOW_ACTIVE_RATIO factor is included; otherwise it's simply
skipped, never fabricated from data this function doesn't have.

Every factor comes from a real, already-persisted signal (active SOS,
active alerts, active WARNING-tier intelligence events) — this module
invents nothing. Same input (the current state of those tables) always
produces the same score: no randomness, no time-of-day weighting, no ML.
"""

from dataclasses import dataclass
from typing import List, Optional

from sqlalchemy.orm import Session

from app.alerts import service as alerts_service
from app.core.config import settings
from app.intelligence import events as intelligence_events
from app.models.enums import AlertSeverity, IntelligenceEventType
from app.models.trip import Trip
from app.schemas.risk import RiskFactor, RiskScore
from app.sos import service as sos_service

# Every WARNING-tier anomaly type risk cares about, and the weight/
# description generator for each. Deliberately mirrors
# app/analytics/safety_analytics.py::ANOMALY_EVENT_TYPES (the same set
# that has an alert policy) — a risk factor never exists for a type that
# was never even eligible to alert anyone.
_PER_EVENT_FACTORS = {
    IntelligenceEventType.GROUP_SEPARATION: (
        "GROUP_SEPARATION", lambda s: s.RISK_WEIGHT_GROUP_SEPARATION,
        lambda n: "The group has split into separate clusters." if n == 1 else f"The group has split apart {n} times.",
    ),
    IntelligenceEventType.ISOLATED_MEMBER: (
        "ISOLATED_MEMBER", lambda s: s.RISK_WEIGHT_ISOLATED_MEMBER,
        lambda n: "A member is isolated from the rest of the group." if n == 1 else f"{n} members are isolated from the group.",
    ),
    IntelligenceEventType.FALLING_BEHIND: (
        "FALLING_BEHIND", lambda s: s.RISK_WEIGHT_FALLING_BEHIND,
        lambda n: "A member is falling behind the group." if n == 1 else f"{n} members are falling behind the group.",
    ),
    IntelligenceEventType.ROUTE_DEVIATION: (
        "ROUTE_DEVIATION", lambda s: s.RISK_WEIGHT_ROUTE_DEVIATION,
        lambda n: "A member has deviated from the planned route." if n == 1 else f"{n} members have deviated from the planned route.",
    ),
    IntelligenceEventType.UNEXPECTED_STOP: (
        "UNEXPECTED_STOP", lambda s: s.RISK_WEIGHT_UNEXPECTED_STOP,
        lambda n: "A member has stopped unexpectedly." if n == 1 else f"{n} members have stopped unexpectedly.",
    ),
    IntelligenceEventType.SPEED_ANOMALY: (
        "SPEED_ANOMALY", lambda s: s.RISK_WEIGHT_SPEED_ANOMALY,
        lambda n: "Unusual speed was detected." if n == 1 else f"Unusual speed was detected for {n} members.",
    ),
}

@dataclass(frozen=True)
class RiskInputs:
    """What calculate_trip_risk() actually looks at — exposed as its own
    type so tests can construct it directly without a database, and so a
    future caller with a different data source (not this DB-query shape)
    can still drive the same scoring logic."""

    active_sos_count: int
    critical_alert_count: int
    active_event_counts: dict  # IntelligenceEventType -> count
    online_count: Optional[int] = None
    member_count: Optional[int] = None


def _level_for_score(score: int) -> str:
    if score <= settings.RISK_LOW_MAX:
        return "LOW"
    if score <= settings.RISK_MEDIUM_MAX:
        return "MEDIUM"
    if score <= settings.RISK_HIGH_MAX:
        return "HIGH"
    return "CRITICAL"


def score_from_inputs(inputs: RiskInputs) -> RiskScore:
    factors: List[RiskFactor] = []

    if inputs.active_sos_count > 0:
        factors.append(
            RiskFactor(
                type="ACTIVE_SOS",
                impact=settings.RISK_WEIGHT_ACTIVE_SOS,
                description=(
                    "An active SOS is present." if inputs.active_sos_count == 1
                    else f"{inputs.active_sos_count} active SOS emergencies are present."
                ),
            )
        )

    if inputs.critical_alert_count > 0:
        factors.append(
            RiskFactor(
                type="CRITICAL_ALERT",
                impact=settings.RISK_WEIGHT_CRITICAL_ALERT,
                description=(
                    "An unresolved critical alert is present." if inputs.critical_alert_count == 1
                    else f"{inputs.critical_alert_count} unresolved critical alerts are present."
                ),
            )
        )

    for event_type, (factor_type, weight_fn, describe) in _PER_EVENT_FACTORS.items():
        count = inputs.active_event_counts.get(event_type, 0)
        if count > 0:
            factors.append(RiskFactor(type=factor_type, impact=weight_fn(settings), description=describe(count)))

    if (
        inputs.online_count is not None
        and inputs.member_count is not None
        and inputs.member_count > 0
        and (inputs.online_count / inputs.member_count) < settings.RISK_LOW_ACTIVE_RATIO_THRESHOLD
    ):
        factors.append(
            RiskFactor(
                type="LOW_ACTIVE_RATIO",
                impact=settings.RISK_WEIGHT_LOW_ACTIVE_RATIO,
                description=f"Only {inputs.online_count} of {inputs.member_count} members are currently online.",
            )
        )

    score = min(100, sum(f.impact for f in factors))
    factors.sort(key=lambda f: f.impact, reverse=True)

    return RiskScore(score=score, level=_level_for_score(score), factors=factors)


def calculate_trip_risk(
    db: Session, trip: Trip, *, online_count: Optional[int] = None, member_count: Optional[int] = None
) -> RiskScore:
    active_sos = sos_service.list_active_sos(db, trip.id)
    active_alerts = alerts_service.list_active_alerts(db, trip.id)
    critical_alert_count = sum(1 for a in active_alerts if a.severity == AlertSeverity.CRITICAL)

    active_events = intelligence_events.list_active_events(db, trip.id)
    event_counts: dict = {}
    for event in active_events:
        if event.event_type in _PER_EVENT_FACTORS:
            event_counts[event.event_type] = event_counts.get(event.event_type, 0) + 1

    inputs = RiskInputs(
        active_sos_count=len(active_sos),
        critical_alert_count=critical_alert_count,
        active_event_counts=event_counts,
        online_count=online_count,
        member_count=member_count,
    )
    return score_from_inputs(inputs)
