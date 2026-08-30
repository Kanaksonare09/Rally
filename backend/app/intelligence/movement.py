"""
Per-member movement classification: MOVING / STOPPED / STALE / OFFLINE.

These four states are a superset of the two IntelligenceEventType values
with the same names (MOVING, STOPPED) — this module decides the member's
*current* state on every evaluation; app/intelligence/detectors.py decides
whether a STOPPED/MOVING *transition* is significant enough to persist as
an UNEXPECTED_STOP intelligence event (persistence-gated, not every
STOPPED classification becomes a database row).

OFFLINE vs STALE, deliberately kept separate per this phase's spec:
  OFFLINE = no WebSocket presence (see app/services/presence_service.py)
  STALE   = presence is fine, but the last GPS point is old
A member can easily be online (chatting on a call, phone screen locked)
without fresh GPS for a bit — that's STALE, not OFFLINE.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass(frozen=True)
class MovementResult:
    state: str  # "MOVING" | "STOPPED" | "STALE" | "OFFLINE"
    # Debounce timer to carry into the next evaluation (Redis-persisted by
    # the caller) — None once a state is confirmed/settled.
    pending_since: Optional[datetime]


def classify_movement_state(
    *,
    speed_mps: Optional[float],
    location_age_seconds: Optional[float],
    presence_online: bool,
    previous_state: Optional[str],
    pending_since: Optional[datetime],
    now: datetime,
    stop_speed_mps: float,
    stop_duration_seconds: int,
    stale_location_seconds: int,
) -> MovementResult:
    """Pure function — no I/O. Callers (app/intelligence/engine.py) own
    reading `previous_state`/`pending_since` from Redis before calling
    this and persisting the result after.

    Hysteresis is one-directional by design: a member registers as MOVING
    the instant their speed clears the threshold (resuming movement after
    a real stop is a time-sensitive signal worth surfacing immediately),
    but a low-speed reading must persist for `stop_duration_seconds`
    before the member is confirmed STOPPED — a single noisy GPS point
    must never flip someone to STOPPED and back.
    """
    if not presence_online:
        return MovementResult(state="OFFLINE", pending_since=None)

    if location_age_seconds is None or location_age_seconds > stale_location_seconds:
        return MovementResult(state="STALE", pending_since=None)

    is_slow = speed_mps is None or speed_mps < stop_speed_mps

    if not is_slow:
        return MovementResult(state="MOVING", pending_since=None)

    if previous_state == "STOPPED":
        return MovementResult(state="STOPPED", pending_since=None)

    if pending_since is None:
        pending_since = now
    elapsed = (now - pending_since).total_seconds()

    if elapsed >= stop_duration_seconds:
        return MovementResult(state="STOPPED", pending_since=None)

    # Still within the debounce window — report the prior confirmed state
    # (defaulting to MOVING, the only sensible prior state for a member
    # who's never been classified yet) while the timer keeps running.
    return MovementResult(state=previous_state or "MOVING", pending_since=pending_since)
