"""Alert / SOS / intelligence-event aggregation — see
GET /trips/{trip_id}/analytics/safety.

"intelligence_events" here is deliberately scoped to the WARNING-tier
anomaly detections (the ones with an alert policy, see
app/alerts/policies.py) — not the routine MOVING/STOPPED/MOVING_TOGETHER
telemetry Phase 7 also stores as intelligence_events rows. Counting those
in would swamp a trip's "what happened" summary with hundreds of routine
transitions that were never meant to be safety signal.
"""

from typing import Dict

from sqlalchemy.orm import Session

from app.alerts import service as alerts_service
from app.intelligence import events as intelligence_events
from app.models.enums import IntelligenceEventType, SOSStatus
from app.models.trip import Trip
from app.schemas.analytics import AlertCounts, IntelligenceEventCounts, SafetyAnalytics, SosCounts
from app.sos import service as sos_service

# The same set app/alerts/policies.py maps to an AlertType — see that
# module's docstring for why the plain movement-state markers have no
# entry there either.
ANOMALY_EVENT_TYPES = {
    IntelligenceEventType.FALLING_BEHIND,
    IntelligenceEventType.GROUP_SEPARATION,
    IntelligenceEventType.ISOLATED_MEMBER,
    IntelligenceEventType.UNEXPECTED_STOP,
    IntelligenceEventType.SPEED_ANOMALY,
    IntelligenceEventType.ROUTE_DEVIATION,
}


def build_safety_analytics(db: Session, trip: Trip) -> SafetyAnalytics:
    alerts = alerts_service.list_alerts(db, trip.id, limit=10000)
    alert_total = len(alerts)
    alert_info = sum(1 for a in alerts if a.severity.value == "INFO")
    alert_warning = sum(1 for a in alerts if a.severity.value == "WARNING")
    alert_critical = sum(1 for a in alerts if a.severity.value == "CRITICAL")

    by_type: Dict[str, int] = {}
    for alert in alerts:
        by_type[alert.alert_type.value] = by_type.get(alert.alert_type.value, 0) + 1

    sos_events = sos_service.list_sos(db, trip.id, limit=10000)
    sos_total = len(sos_events)
    sos_resolved = sum(1 for s in sos_events if s.status == SOSStatus.RESOLVED)
    sos_cancelled = sum(1 for s in sos_events if s.status == SOSStatus.CANCELLED)

    anomaly_events = [
        event
        for event in intelligence_events.list_events(db, trip.id, limit=10000)
        if event.event_type in ANOMALY_EVENT_TYPES
    ]
    anomaly_total = len(anomaly_events)
    anomaly_resolved = sum(1 for e in anomaly_events if e.resolved_at is not None)
    anomaly_active = anomaly_total - anomaly_resolved

    return SafetyAnalytics(
        alerts=AlertCounts(total=alert_total, info=alert_info, warning=alert_warning, critical=alert_critical),
        by_type=by_type,
        sos=SosCounts(total=sos_total, resolved=sos_resolved, cancelled=sos_cancelled),
        intelligence_events=IntelligenceEventCounts(
            total=anomaly_total, resolved=anomaly_resolved, active=anomaly_active
        ),
    )
