"""
app/analytics/safety_analytics.py — aggregates existing alert/SOS/
intelligence-event service functions rather than querying directly, so
these tests patch those service functions (same pattern as the rest of
this codebase's API-level tests) rather than needing a live database.
"""

import uuid
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import patch

from app.analytics.safety_analytics import build_safety_analytics
from app.models.enums import (
    AlertSeverity,
    AlertType,
    IntelligenceEventType,
    IntelligenceSeverity,
    SOSStatus,
)

TRIP_ID = uuid.uuid4()


def make_alert(alert_type=AlertType.FALLING_BEHIND, severity=AlertSeverity.WARNING):
    return SimpleNamespace(alert_type=alert_type, severity=severity)


def make_sos(status=SOSStatus.ACTIVE):
    return SimpleNamespace(status=status)


def make_event(event_type=IntelligenceEventType.FALLING_BEHIND, resolved=False):
    return SimpleNamespace(
        event_type=event_type,
        resolved_at=datetime.now(timezone.utc) if resolved else None,
    )


def make_trip():
    return SimpleNamespace(id=TRIP_ID)


@patch("app.analytics.safety_analytics.intelligence_events.list_events")
@patch("app.analytics.safety_analytics.sos_service.list_sos")
@patch("app.analytics.safety_analytics.alerts_service.list_alerts")
def test_alert_severity_counts(mock_alerts, mock_sos, mock_events):
    mock_alerts.return_value = [
        make_alert(severity=AlertSeverity.WARNING),
        make_alert(severity=AlertSeverity.WARNING),
        make_alert(severity=AlertSeverity.CRITICAL),
    ]
    mock_sos.return_value = []
    mock_events.return_value = []

    result = build_safety_analytics(None, make_trip())

    assert result.alerts.total == 3
    assert result.alerts.warning == 2
    assert result.alerts.critical == 1
    assert result.alerts.info == 0


@patch("app.analytics.safety_analytics.intelligence_events.list_events")
@patch("app.analytics.safety_analytics.sos_service.list_sos")
@patch("app.analytics.safety_analytics.alerts_service.list_alerts")
def test_alert_by_type_breakdown(mock_alerts, mock_sos, mock_events):
    mock_alerts.return_value = [
        make_alert(alert_type=AlertType.FALLING_BEHIND),
        make_alert(alert_type=AlertType.FALLING_BEHIND),
        make_alert(alert_type=AlertType.ROUTE_DEVIATION),
    ]
    mock_sos.return_value = []
    mock_events.return_value = []

    result = build_safety_analytics(None, make_trip())

    assert result.by_type == {"FALLING_BEHIND": 2, "ROUTE_DEVIATION": 1}


@patch("app.analytics.safety_analytics.intelligence_events.list_events")
@patch("app.analytics.safety_analytics.sos_service.list_sos")
@patch("app.analytics.safety_analytics.alerts_service.list_alerts")
def test_sos_counts_resolved_and_cancelled(mock_alerts, mock_sos, mock_events):
    mock_alerts.return_value = []
    mock_sos.return_value = [make_sos(SOSStatus.RESOLVED), make_sos(SOSStatus.CANCELLED), make_sos(SOSStatus.ACTIVE)]
    mock_events.return_value = []

    result = build_safety_analytics(None, make_trip())

    assert result.sos.total == 3
    assert result.sos.resolved == 1
    assert result.sos.cancelled == 1


@patch("app.analytics.safety_analytics.intelligence_events.list_events")
@patch("app.analytics.safety_analytics.sos_service.list_sos")
@patch("app.analytics.safety_analytics.alerts_service.list_alerts")
def test_intelligence_events_scoped_to_anomaly_types_only(mock_alerts, mock_sos, mock_events):
    """MOVING/STOPPED/MOVING_TOGETHER telemetry must not dominate the
    safety summary's intelligence_events count."""
    mock_alerts.return_value = []
    mock_sos.return_value = []
    mock_events.return_value = [
        make_event(IntelligenceEventType.FALLING_BEHIND, resolved=True),
        make_event(IntelligenceEventType.ROUTE_DEVIATION, resolved=False),
        make_event(IntelligenceEventType.MOVING, resolved=True),
        make_event(IntelligenceEventType.STOPPED, resolved=True),
        make_event(IntelligenceEventType.MOVING_TOGETHER, resolved=True),
    ]

    result = build_safety_analytics(None, make_trip())

    assert result.intelligence_events.total == 2
    assert result.intelligence_events.resolved == 1
    assert result.intelligence_events.active == 1


@patch("app.analytics.safety_analytics.intelligence_events.list_events")
@patch("app.analytics.safety_analytics.sos_service.list_sos")
@patch("app.analytics.safety_analytics.alerts_service.list_alerts")
def test_no_alerts_or_sos_is_zero_not_null(mock_alerts, mock_sos, mock_events):
    mock_alerts.return_value = []
    mock_sos.return_value = []
    mock_events.return_value = []

    result = build_safety_analytics(None, make_trip())

    assert result.alerts.total == 0
    assert result.sos.total == 0
    assert result.intelligence_events.total == 0
