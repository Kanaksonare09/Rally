"""
WebSocket connect-time auth/authorization, unit-tested against a fake DB
session (no live database — see backend README). Mirrors the FakeSession
pattern already used for trip_service/location_service tests.
"""

import uuid
from types import SimpleNamespace

import pytest

from app.models.enums import MemberRole, MemberStatus, TripStatus
from app.websocket.auth import WebSocketAuthError, _load_trip_and_membership, authenticate_token
from tests.conftest import DEFAULT_TEST_USER_ID, make_token

TRIP_ID = uuid.uuid4()
GROUP_ID = uuid.uuid4()
USER_ID = uuid.UUID(DEFAULT_TEST_USER_ID)


class _ScalarResult:
    def __init__(self, value):
        self._value = value

    def first(self):
        return self._value


class FakeSession:
    def __init__(self, trip=None, member=None):
        self._trip = trip
        self._member = member

    def get(self, model, pk):
        return self._trip

    def scalars(self, stmt):
        return _ScalarResult(self._member)


def make_trip(status=TripStatus.ACTIVE, **overrides):
    trip = SimpleNamespace(id=TRIP_ID, group_id=GROUP_ID, status=status)
    for k, v in overrides.items():
        setattr(trip, k, v)
    return trip


def make_member(status=MemberStatus.ACTIVE, role=MemberRole.MEMBER):
    return SimpleNamespace(user_id=USER_ID, role=role, status=status)


# ---- authenticate_token ----------------------------------------------


def test_authenticate_token_returns_user_id_for_valid_token():
    token = make_token(sub=DEFAULT_TEST_USER_ID)
    assert authenticate_token(token) == DEFAULT_TEST_USER_ID


def test_authenticate_token_rejects_missing_token():
    with pytest.raises(WebSocketAuthError) as exc_info:
        authenticate_token(None)
    assert exc_info.value.code == "UNAUTHORIZED"


def test_authenticate_token_rejects_empty_token():
    with pytest.raises(WebSocketAuthError) as exc_info:
        authenticate_token("")
    assert exc_info.value.code == "UNAUTHORIZED"


def test_authenticate_token_rejects_invalid_jwt():
    with pytest.raises(WebSocketAuthError) as exc_info:
        authenticate_token("this-is-not-a-jwt")
    assert exc_info.value.code == "UNAUTHORIZED"


def test_authenticate_token_rejects_expired_jwt():
    token = make_token(expires_in_seconds=-60)
    with pytest.raises(WebSocketAuthError) as exc_info:
        authenticate_token(token)
    assert exc_info.value.code == "UNAUTHORIZED"


def test_authenticate_token_never_leaks_the_token_in_the_error():
    token = make_token(expires_in_seconds=-60)
    with pytest.raises(WebSocketAuthError) as exc_info:
        authenticate_token(token)
    assert token not in str(exc_info.value)


# ---- _load_trip_and_membership -----------------------------------------


def test_authorize_rejects_nonexistent_trip():
    db = FakeSession(trip=None, member=None)
    with pytest.raises(WebSocketAuthError) as exc_info:
        _load_trip_and_membership(db, TRIP_ID, USER_ID)
    assert exc_info.value.code == "TRIP_NOT_FOUND"


def test_authorize_rejects_non_member():
    db = FakeSession(trip=make_trip(), member=None)
    with pytest.raises(WebSocketAuthError) as exc_info:
        _load_trip_and_membership(db, TRIP_ID, USER_ID)
    assert exc_info.value.code == "NOT_A_MEMBER"


def test_authorize_rejects_removed_member():
    db = FakeSession(trip=make_trip(), member=make_member(status=MemberStatus.REMOVED))
    with pytest.raises(WebSocketAuthError) as exc_info:
        _load_trip_and_membership(db, TRIP_ID, USER_ID)
    assert exc_info.value.code == "NOT_A_MEMBER"


def test_authorize_rejects_inactive_trip_for_a_real_member():
    db = FakeSession(trip=make_trip(status=TripStatus.CREATED), member=make_member())
    with pytest.raises(WebSocketAuthError) as exc_info:
        _load_trip_and_membership(db, TRIP_ID, USER_ID)
    assert exc_info.value.code == "TRIP_NOT_ACTIVE"


def test_authorize_membership_checked_before_trip_status():
    """A non-member of a CREATED (non-active) trip must be rejected as
    NOT_A_MEMBER, not TRIP_NOT_ACTIVE — membership is checked first so an
    outsider learns nothing about the trip's status (security section
    item 1)."""
    db = FakeSession(trip=make_trip(status=TripStatus.CREATED), member=None)
    with pytest.raises(WebSocketAuthError) as exc_info:
        _load_trip_and_membership(db, TRIP_ID, USER_ID)
    assert exc_info.value.code == "NOT_A_MEMBER"


def test_authorize_succeeds_for_active_member_of_active_trip():
    db = FakeSession(trip=make_trip(status=TripStatus.ACTIVE), member=make_member(role=MemberRole.LEADER))
    ctx = _load_trip_and_membership(db, TRIP_ID, USER_ID)

    assert ctx.user_id == USER_ID
    assert ctx.trip_id == TRIP_ID
    assert ctx.group_id == GROUP_ID
    assert ctx.role == MemberRole.LEADER
