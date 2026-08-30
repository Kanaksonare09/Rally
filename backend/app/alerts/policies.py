"""
Alert policy: whether an intelligence event becomes a user-facing alert,
and with what severity/title/message. This is the ONLY place that
decision lives — the intelligence detectors know nothing about alerts,
and app/alerts/service.py knows nothing about how an event was detected,
only what (type, severity, metadata) it carries.

Deliberately a plain dict, not a database table — "should this become an
alert" is a code-level policy decision for this phase, same spirit as the
threshold constants in app/intelligence/thresholds.py. INFO-level
intelligence events (MOVING_TOGETHER, STOPPED, MOVING) have no entry here
on purpose: "do not create alerts for every INFO-level state."
"""

from dataclasses import dataclass
from typing import Callable, Dict, Optional

from app.models.enums import AlertSeverity, AlertType, IntelligenceEventType


@dataclass(frozen=True)
class AlertPolicy:
    alert_type: AlertType
    severity: AlertSeverity
    title: str
    message_fn: Callable[[dict], str]


def _falling_behind_message(metadata: dict) -> str:
    distance = metadata.get("distance_meters")
    suffix = f" ({distance:.0f}m from the group)" if isinstance(distance, (int, float)) else ""
    return f"A group member is falling behind{suffix}."


def _group_separation_message(metadata: dict) -> str:
    sizes = metadata.get("cluster_sizes")
    suffix = f" ({'/'.join(str(s) for s in sizes)} split)" if sizes else ""
    return f"The group has split into separate clusters{suffix}."


def _isolated_member_message(metadata: dict) -> str:
    distance = metadata.get("nearest_member_distance_meters")
    suffix = f" (nearest member is {distance:.0f}m away)" if isinstance(distance, (int, float)) else ""
    return f"A group member is isolated from everyone else{suffix}."


def _unexpected_stop_message(metadata: dict) -> str:
    return "A group member has stopped while the rest of the group keeps moving."


def _speed_anomaly_message(metadata: dict) -> str:
    speed = metadata.get("observed_speed_mps")
    suffix = f" ({speed:.1f} m/s)" if isinstance(speed, (int, float)) else ""
    return f"Unusually high speed detected{suffix}."


def _route_deviation_message(metadata: dict) -> str:
    distance = metadata.get("distance_from_route_meters")
    suffix = f" ({distance:.0f}m from the planned route)" if isinstance(distance, (int, float)) else ""
    return f"A group member has deviated from the planned route{suffix}."


_POLICIES: Dict[IntelligenceEventType, AlertPolicy] = {
    IntelligenceEventType.FALLING_BEHIND: AlertPolicy(
        AlertType.FALLING_BEHIND, AlertSeverity.WARNING, "Member falling behind", _falling_behind_message
    ),
    IntelligenceEventType.GROUP_SEPARATION: AlertPolicy(
        AlertType.GROUP_SEPARATION, AlertSeverity.WARNING, "Group has separated", _group_separation_message
    ),
    IntelligenceEventType.ISOLATED_MEMBER: AlertPolicy(
        AlertType.ISOLATED_MEMBER, AlertSeverity.WARNING, "Member isolated", _isolated_member_message
    ),
    IntelligenceEventType.UNEXPECTED_STOP: AlertPolicy(
        AlertType.UNEXPECTED_STOP, AlertSeverity.WARNING, "Unexpected stop", _unexpected_stop_message
    ),
    IntelligenceEventType.SPEED_ANOMALY: AlertPolicy(
        AlertType.SPEED_ANOMALY, AlertSeverity.WARNING, "Unusual speed detected", _speed_anomaly_message
    ),
    # Phase 9 — routed through this exact same table, no separate alert
    # architecture for route events.
    IntelligenceEventType.ROUTE_DEVIATION: AlertPolicy(
        AlertType.ROUTE_DEVIATION, AlertSeverity.WARNING, "Route deviation", _route_deviation_message
    ),
}


def get_policy(event_type: IntelligenceEventType) -> Optional[AlertPolicy]:
    return _POLICIES.get(event_type)
