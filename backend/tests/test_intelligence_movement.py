from datetime import datetime, timedelta, timezone

import pytest

from app.intelligence.movement import classify_movement_state

NOW = datetime(2026, 8, 30, 12, 0, 0, tzinfo=timezone.utc)

DEFAULTS = dict(stop_speed_mps=0.8, stop_duration_seconds=120, stale_location_seconds=60)


def classify(**overrides):
    kwargs = dict(
        speed_mps=5.0,
        location_age_seconds=2.0,
        presence_online=True,
        previous_state=None,
        pending_since=None,
        now=NOW,
        **DEFAULTS,
    )
    kwargs.update(overrides)
    return classify_movement_state(**kwargs)


def test_moving_user_detected():
    result = classify(speed_mps=5.0)
    assert result.state == "MOVING"
    assert result.pending_since is None


def test_offline_user_detected_regardless_of_speed():
    result = classify(presence_online=False, speed_mps=10.0)
    assert result.state == "OFFLINE"


def test_stale_location_detected_when_online():
    """Online (WebSocket connected) but no fresh GPS — STALE, not OFFLINE,
    per this phase's explicit distinction between presence and freshness."""
    result = classify(presence_online=True, location_age_seconds=120, stale_location_seconds=60)
    assert result.state == "STALE"


def test_offline_takes_precedence_over_stale():
    result = classify(presence_online=False, location_age_seconds=None)
    assert result.state == "OFFLINE"


def test_no_location_data_at_all_is_stale():
    result = classify(location_age_seconds=None, presence_online=True)
    assert result.state == "STALE"


def test_temporary_low_speed_does_not_immediately_create_stopped():
    """A single slow reading must not flip an actively-moving member to
    STOPPED — the debounce timer starts, but the confirmed state doesn't
    change until it accumulates the full stop_duration_seconds."""
    result = classify(speed_mps=0.1, previous_state="MOVING", pending_since=None, stop_duration_seconds=120)
    assert result.state == "MOVING"
    assert result.pending_since == NOW


def test_persistent_low_speed_creates_stopped():
    pending_since = NOW - timedelta(seconds=150)  # already past the 120s threshold
    result = classify(speed_mps=0.1, previous_state="MOVING", pending_since=pending_since, stop_duration_seconds=120)
    assert result.state == "STOPPED"
    assert result.pending_since is None


def test_low_speed_exactly_at_threshold_confirms_stopped():
    pending_since = NOW - timedelta(seconds=120)
    result = classify(speed_mps=0.1, previous_state="MOVING", pending_since=pending_since, stop_duration_seconds=120)
    assert result.state == "STOPPED"


def test_low_speed_just_under_threshold_stays_pending():
    pending_since = NOW - timedelta(seconds=119)
    result = classify(speed_mps=0.1, previous_state="MOVING", pending_since=pending_since, stop_duration_seconds=120)
    assert result.state == "MOVING"
    assert result.pending_since == pending_since


def test_resuming_speed_immediately_clears_stopped():
    """Unlike entering STOPPED, resuming MOVING is immediate — a member
    who starts moving again shouldn't stay reported as STOPPED."""
    result = classify(speed_mps=5.0, previous_state="STOPPED", pending_since=None)
    assert result.state == "MOVING"


def test_already_confirmed_stopped_stays_stopped_without_a_new_timer():
    result = classify(speed_mps=0.1, previous_state="STOPPED", pending_since=None)
    assert result.state == "STOPPED"
    assert result.pending_since is None


def test_no_speed_reading_is_treated_as_slow():
    result = classify(speed_mps=None, previous_state="MOVING", pending_since=None)
    assert result.state == "MOVING"  # pending, not yet confirmed
    assert result.pending_since == NOW


def test_first_ever_classification_with_no_previous_state_defaults_sensibly():
    """A brand new member with no prior state and a slow reading
    shouldn't crash or default to something nonsensical."""
    result = classify(speed_mps=0.1, previous_state=None, pending_since=None)
    assert result.state == "MOVING"  # still within the debounce window
    assert result.pending_since == NOW
