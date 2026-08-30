import uuid
import pytest
from unittest.mock import MagicMock, patch, AsyncMock
from fastapi.testclient import TestClient
from app.main import app
from app.models.enums import MemberStatus, TripStatus
from tests.conftest import DEFAULT_TEST_USER_ID, make_token
import json

client = TestClient(app)
GROUP_ID = uuid.uuid4()
TRIP_ID = uuid.uuid4()
USER_ID = uuid.UUID(DEFAULT_TEST_USER_ID)

@pytest.fixture
def mock_redis():
    mock_r = AsyncMock()
    mock_r.hgetall.return_value = {}
    mock_r.hget.return_value = None
    with patch("app.websocket.router.get_redis") as mock_get_redis:
        async def mock_gen():
            yield mock_r
        mock_get_redis.return_value = mock_gen()
        yield mock_r

@pytest.fixture
def mock_db_scope():
    mock_db = MagicMock()
    
    # Mocking member lookup (always active)
    mock_member = MagicMock()
    mock_member.status = MemberStatus.ACTIVE
    
    # Mocking active trip lookup
    mock_trip = MagicMock()
    mock_trip.id = TRIP_ID
    mock_trip.group_id = GROUP_ID
    mock_trip.status = TripStatus.ACTIVE
    
    # Simple side effect to return member for first query and trip for second query
    def mock_scalars(stmt):
        class MockResult:
            def first(self):
                stmt_str = str(stmt).lower()
                if "group_member" in stmt_str:
                    return mock_member
                if "trip" in stmt_str:
                    return mock_trip
                return None
        return MockResult()
        
    mock_db.scalars.side_effect = mock_scalars
    
    class MockScope:
        def __enter__(self):
            return mock_db
        def __exit__(self, exc_type, exc_val, exc_tb):
            pass
            
    with patch("app.websocket.router.session_scope", return_value=MockScope()):
        yield mock_db

def test_unauthenticated_connection_rejected():
    from starlette.websockets import WebSocketDisconnect
    with client.websocket_connect(f"/ws/groups/{GROUP_ID}?token=invalid") as websocket:
        data = websocket.receive_json()
        assert data["type"] == "error"
        assert data["data"]["code"] == "UNAUTHORIZED"
        with pytest.raises(WebSocketDisconnect) as exc:
            websocket.receive_text()
        assert exc.value.code == 1008

@patch("app.websocket.router.location_service.record_location")
def test_valid_connection_and_location_update(mock_record_location, mock_db_scope, mock_redis):
    token = make_token(sub=DEFAULT_TEST_USER_ID)
    
    with client.websocket_connect(f"/ws/groups/{GROUP_ID}?token={token}") as websocket:
        # First message should be group_state
        data = websocket.receive_json()
        assert data["type"] == "group_state"
        assert data["data"]["group_id"] == str(GROUP_ID)
        
        # Send location update
        loc_data = {
            "type": "location_update",
            "data": {
                "latitude": 22.0,
                "longitude": 75.0,
                "accuracy": 10.0,
                "speed": 5.0,
                "heading": 90.0,
                "recorded_at": "2026-08-26T10:00:00Z"
            }
        }
        websocket.send_json(loc_data)
        
        # We shouldn't receive our own broadcast back per logic (exclude_user_id)
        # But we can verify the mock was called
        import time
        time.sleep(0.1) # give time for async task if any
        assert mock_record_location.called
        assert mock_redis.hset.called
        
def test_ping_pong(mock_db_scope, mock_redis):
    token = make_token(sub=DEFAULT_TEST_USER_ID)
    
    with client.websocket_connect(f"/ws/groups/{GROUP_ID}?token={token}") as websocket:
        # consume group state
        websocket.receive_json()
        
        # send ping
        websocket.send_json({"type": "ping"})
        
        # expect pong
        data = websocket.receive_json()
        assert data["type"] == "pong"
        assert "timestamp" in data["data"]
