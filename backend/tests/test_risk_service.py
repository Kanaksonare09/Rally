"""
app/risk/service.py: deterministic scoring from RiskInputs directly (no
DB needed — score_from_inputs is the pure calculation core;
calculate_trip_risk is the thin DB-query wrapper around it, exercised
separately in test_risk_api.py via mocked service calls).
"""

from app.models.enums import IntelligenceEventType
from app.risk.service import RiskInputs, score_from_inputs

EMPTY = RiskInputs(active_sos_count=0, critical_alert_count=0, active_event_counts={})


def test_no_signals_is_zero_score_low_level():
    result = score_from_inputs(EMPTY)
    assert result.score == 0
    assert result.level == "LOW"
    assert result.factors == []


def test_same_input_always_produces_the_same_score():
    a = score_from_inputs(RiskInputs(active_sos_count=1, critical_alert_count=1, active_event_counts={}))
    b = score_from_inputs(RiskInputs(active_sos_count=1, critical_alert_count=1, active_event_counts={}))
    assert a.score == b.score
    assert a.level == b.level


def test_active_sos_dominates_the_score():
    result = score_from_inputs(RiskInputs(active_sos_count=1, critical_alert_count=0, active_event_counts={}))
    assert result.score == 50  # RISK_WEIGHT_ACTIVE_SOS default
    factor = result.factors[0]
    assert factor.type == "ACTIVE_SOS"
    assert "active SOS" in factor.description


def test_critical_alert_increases_score():
    result = score_from_inputs(RiskInputs(active_sos_count=0, critical_alert_count=1, active_event_counts={}))
    assert result.score == 30  # RISK_WEIGHT_CRITICAL_ALERT default
    assert result.factors[0].type == "CRITICAL_ALERT"


def test_group_separation_factor():
    result = score_from_inputs(
        RiskInputs(active_sos_count=0, critical_alert_count=0, active_event_counts={IntelligenceEventType.GROUP_SEPARATION: 1})
    )
    assert result.score == 17
    assert result.factors[0].type == "GROUP_SEPARATION"


def test_low_level_classification():
    result = score_from_inputs(RiskInputs(active_sos_count=0, critical_alert_count=0, active_event_counts={IntelligenceEventType.SPEED_ANOMALY: 1}))
    assert result.score == 8
    assert result.level == "LOW"


def test_medium_level_classification():
    result = score_from_inputs(
        RiskInputs(
            active_sos_count=0, critical_alert_count=1,
            active_event_counts={IntelligenceEventType.GROUP_SEPARATION: 1, IntelligenceEventType.FALLING_BEHIND: 1},
        )
    )
    # 30 + 17 + 10 = 57
    assert result.score == 57
    assert result.level == "MEDIUM"


def test_high_level_classification():
    result = score_from_inputs(
        RiskInputs(
            active_sos_count=0, critical_alert_count=1,
            active_event_counts={
                IntelligenceEventType.GROUP_SEPARATION: 1,
                IntelligenceEventType.ISOLATED_MEMBER: 1,
                IntelligenceEventType.FALLING_BEHIND: 1,
            },
        )
    )
    # 30 + 17 + 12 + 10 = 69
    assert result.score == 69
    assert result.level == "HIGH"


def test_critical_level_classification():
    result = score_from_inputs(RiskInputs(active_sos_count=1, critical_alert_count=1, active_event_counts={IntelligenceEventType.GROUP_SEPARATION: 1}))
    # 50 + 30 + 17 = 97
    assert result.score == 97
    assert result.level == "CRITICAL"


def test_score_never_exceeds_100():
    result = score_from_inputs(
        RiskInputs(
            active_sos_count=3, critical_alert_count=5,
            active_event_counts={t: 5 for t in IntelligenceEventType if t.name in (
                "GROUP_SEPARATION", "ISOLATED_MEMBER", "FALLING_BEHIND", "ROUTE_DEVIATION", "UNEXPECTED_STOP", "SPEED_ANOMALY"
            )},
        )
    )
    assert result.score == 100
    assert result.level == "CRITICAL"


def test_multiple_falling_behind_members_counted_once_as_a_factor_not_per_member():
    """count=3 falling-behind members still produces exactly one
    FALLING_BEHIND factor (with a description reflecting the count), not
    three separate factors that could balloon the score unpredictably."""
    result = score_from_inputs(RiskInputs(active_sos_count=0, critical_alert_count=0, active_event_counts={IntelligenceEventType.FALLING_BEHIND: 3}))
    falling_behind_factors = [f for f in result.factors if f.type == "FALLING_BEHIND"]
    assert len(falling_behind_factors) == 1
    assert result.score == 10
    assert "3 members" in falling_behind_factors[0].description


def test_low_active_ratio_factor_only_applied_when_data_available():
    without_data = score_from_inputs(RiskInputs(active_sos_count=0, critical_alert_count=0, active_event_counts={}))
    assert without_data.score == 0  # no fabricated factor when online/member counts aren't supplied

    with_low_ratio = score_from_inputs(
        RiskInputs(active_sos_count=0, critical_alert_count=0, active_event_counts={}, online_count=1, member_count=4)
    )
    assert with_low_ratio.score == 10
    assert with_low_ratio.factors[0].type == "LOW_ACTIVE_RATIO"


def test_healthy_active_ratio_produces_no_factor():
    result = score_from_inputs(
        RiskInputs(active_sos_count=0, critical_alert_count=0, active_event_counts={}, online_count=4, member_count=4)
    )
    assert result.score == 0


def test_factors_sorted_by_impact_descending():
    result = score_from_inputs(
        RiskInputs(
            active_sos_count=0, critical_alert_count=1,
            active_event_counts={IntelligenceEventType.SPEED_ANOMALY: 1, IntelligenceEventType.GROUP_SEPARATION: 1},
        )
    )
    impacts = [f.impact for f in result.factors]
    assert impacts == sorted(impacts, reverse=True)
