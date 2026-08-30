from app.alerts.policies import get_policy
from app.models.enums import AlertSeverity, AlertType, IntelligenceEventType

WARNING_TYPES = [
    IntelligenceEventType.FALLING_BEHIND,
    IntelligenceEventType.GROUP_SEPARATION,
    IntelligenceEventType.ISOLATED_MEMBER,
    IntelligenceEventType.UNEXPECTED_STOP,
    IntelligenceEventType.SPEED_ANOMALY,
    IntelligenceEventType.ROUTE_DEVIATION,  # Phase 9
]

INFO_TYPES = [
    IntelligenceEventType.MOVING_TOGETHER,
    IntelligenceEventType.STOPPED,
    IntelligenceEventType.MOVING,
]


def test_every_warning_intelligence_type_has_a_policy():
    for event_type in WARNING_TYPES:
        assert get_policy(event_type) is not None


def test_info_level_states_have_no_alert_policy():
    """MOVING_TOGETHER/STOPPED/MOVING must never generate alerts unless
    explicitly configured — this phase configures none of them."""
    for event_type in INFO_TYPES:
        assert get_policy(event_type) is None


def test_policies_use_warning_severity_not_critical():
    """Nothing is blindly marked CRITICAL in this phase."""
    for event_type in WARNING_TYPES:
        policy = get_policy(event_type)
        assert policy.severity == AlertSeverity.WARNING


def test_policy_alert_type_matches_source_event_type():
    for event_type in WARNING_TYPES:
        policy = get_policy(event_type)
        assert policy.alert_type.value == event_type.value


def test_message_fn_produces_readable_text_with_metadata():
    policy = get_policy(IntelligenceEventType.FALLING_BEHIND)
    message = policy.message_fn({"distance_meters": 650})
    assert "650" in message


def test_message_fn_handles_missing_metadata_gracefully():
    for event_type in WARNING_TYPES:
        policy = get_policy(event_type)
        message = policy.message_fn({})
        assert isinstance(message, str) and len(message) > 0


def test_route_deviation_message_includes_distance():
    policy = get_policy(IntelligenceEventType.ROUTE_DEVIATION)
    message = policy.message_fn({"distance_from_route_meters": 180})
    assert "180" in message
