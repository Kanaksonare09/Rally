import uuid

import pytest
from pydantic import ValidationError

from app.websocket.schemas import (
    ClientEnvelope,
    ErrorCode,
    LocationCreate,
    PresenceStatus,
    build_error,
    build_heartbeat_ack,
    build_location_ack,
    build_location_update_event,
    build_presence_update,
    build_route_deviation,
    build_route_progress,
    build_trip_ended,
    build_trip_state,
)

USER_ID = uuid.uuid4()
TRIP_ID = uuid.uuid4()


def test_client_envelope_parses_type_and_data():
    envelope = ClientEnvelope.model_validate({"type": "location_update", "data": {"latitude": 1, "longitude": 1}})
    assert envelope.type == "location_update"
    assert envelope.data == {"latitude": 1, "longitude": 1}


def test_client_envelope_data_is_optional():
    envelope = ClientEnvelope.model_validate({"type": "heartbeat"})
    assert envelope.data is None


def test_client_envelope_requires_type():
    with pytest.raises(ValidationError):
        ClientEnvelope.model_validate({"data": {}})


def test_location_create_has_no_trusted_identity_fields():
    """Same trust boundary as the REST endpoint — the client can never
    smuggle in user_id/trip_id/group_id via a WebSocket message either."""
    forbidden = {"id", "trip_id", "group_id", "user_id", "created_at"}
    assert forbidden.isdisjoint(LocationCreate.model_fields.keys())


def test_build_error_accepts_error_code_enum():
    msg = build_error(ErrorCode.INVALID_LOCATION, "bad coords")
    assert msg == {"type": "error", "data": {"code": "INVALID_LOCATION", "message": "bad coords"}}


def test_build_error_accepts_plain_string_code():
    """WebSocketAuthError/AppHTTPException both carry codes as plain
    strings, not the ErrorCode enum — build_error must handle both."""
    msg = build_error("NOT_A_MEMBER", "nope")
    assert msg["data"]["code"] == "NOT_A_MEMBER"


def test_build_location_ack_shape():
    msg = build_location_ack(recorded_at="2026-08-30T10:00:00Z", accepted=True)
    assert msg == {"type": "location_ack", "data": {"recorded_at": "2026-08-30T10:00:00Z", "accepted": True}}


def test_build_location_ack_can_be_rejected():
    msg = build_location_ack(recorded_at="2026-08-30T10:00:00Z", accepted=False)
    assert msg["data"]["accepted"] is False


def test_build_heartbeat_ack_shape():
    msg = build_heartbeat_ack()
    assert msg["type"] == "heartbeat_ack"
    assert "server_time" in msg["data"]


def test_build_location_update_event_never_leaks_extra_fields():
    msg = build_location_update_event(
        user_id=USER_ID, latitude=1.0, longitude=2.0, accuracy=3.0, speed=4.0, heading=5.0,
        recorded_at="2026-08-30T10:00:00Z",
    )
    assert msg["type"] == "location_update"
    assert msg["data"]["user_id"] == str(USER_ID)
    assert set(msg["data"].keys()) == {
        "user_id", "latitude", "longitude", "accuracy", "speed", "heading", "recorded_at", "updated_at"
    }


def test_build_presence_update_online():
    msg = build_presence_update(USER_ID, PresenceStatus.ONLINE)
    assert msg == {"type": "presence_update", "data": {"user_id": str(USER_ID), "status": "ONLINE"}}


def test_build_presence_update_offline():
    msg = build_presence_update(USER_ID, PresenceStatus.OFFLINE)
    assert msg["data"]["status"] == "OFFLINE"


def test_build_trip_state_shape():
    members = [{"user_id": str(USER_ID), "status": "ONLINE"}]
    msg = build_trip_state(TRIP_ID, members)
    assert msg == {"type": "trip_state", "data": {"trip_id": str(TRIP_ID), "members": members}}


def test_build_trip_ended_shape():
    msg = build_trip_ended(TRIP_ID, "COMPLETED")
    assert msg == {"type": "trip_ended", "data": {"trip_id": str(TRIP_ID), "status": "COMPLETED"}}


# ---- Phase 9: route_progress / route_deviation ----------------------------


def test_build_route_progress_shape():
    ROUTE_ID = uuid.uuid4()
    members = [{"user_id": str(USER_ID), "route_state": "ON_ROUTE", "route_fraction": 0.4}]
    msg = build_route_progress(
        trip_id=TRIP_ID, route_id=ROUTE_ID, group_route_fraction=0.4, trip_arrived=False, members=members
    )
    assert msg["type"] == "route_progress"
    assert msg["data"]["trip_id"] == str(TRIP_ID)
    assert msg["data"]["route_id"] == str(ROUTE_ID)
    assert msg["data"]["group_route_fraction"] == 0.4
    assert msg["data"]["trip_arrived"] is False
    assert msg["data"]["members"] == members
    assert "server_time" in msg["data"]


def test_build_route_progress_allows_none_group_fraction():
    """No eligible (online, fresh-location) member yet -> no median to
    report, not a crash."""
    msg = build_route_progress(trip_id=TRIP_ID, route_id=uuid.uuid4(), group_route_fraction=None, trip_arrived=False, members=[])
    assert msg["data"]["group_route_fraction"] is None


def test_build_route_deviation_shape():
    msg = build_route_deviation(
        user_id=USER_ID, distance_from_route_meters=180.5, status="DEVIATED", detected_at="2026-08-30T10:00:00Z"
    )
    assert msg == {
        "type": "route_deviation",
        "data": {
            "user_id": str(USER_ID),
            "distance_from_route_meters": 180.5,
            "status": "DEVIATED",
            "detected_at": "2026-08-30T10:00:00Z",
        },
    }


def test_build_route_deviation_back_on_route():
    msg = build_route_deviation(
        user_id=USER_ID, distance_from_route_meters=40.0, status="BACK_ON_ROUTE", detected_at="2026-08-30T10:05:00Z"
    )
    assert msg["data"]["status"] == "BACK_ON_ROUTE"
