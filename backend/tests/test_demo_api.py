"""
app/api/demo.py — endpoint-level tests. The real app.main.app singleton
is built once at import time with whatever DEMO_MODE this test process
started with (False, per the default settings/tests/conftest.py never
sets it) — used directly to prove demo routes are genuinely absent (404,
not 403) when disabled, exactly as Part 7 requires. For the "demo mode
enabled" behavior, a separate minimal FastAPI app mounting only
app.api.demo.router is used instead of re-importing app.main under
different settings (Python's module cache would just return the
already-imported instance).
"""

import uuid
from unittest.mock import AsyncMock, patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.demo import router as demo_router
from app.core.config import settings
from app.main import app as real_app

real_client = TestClient(real_app)
API = settings.API_V1_STR

demo_app = FastAPI()
demo_app.include_router(demo_router, prefix=API)
demo_client = TestClient(demo_app)


# ---- disabled by default (the real app, DEMO_MODE=False in tests) ---------


def test_demo_routes_do_not_exist_when_demo_mode_disabled():
    for method, path in [
        ("post", f"{API}/demo/reset"),
        ("post", f"{API}/demo/scenarios/normal/start"),
        ("post", f"{API}/demo/scenarios/normal/stop"),
        ("get", f"{API}/demo/status"),
    ]:
        response = getattr(real_client, method)(path)
        # A real 404 (route not found) — not a 403 — proving these
        # endpoints are entirely absent from the router, not merely
        # access-denied. See app/main.py's conditional include_router.
        assert response.status_code == 404, (method, path)


def test_demo_mode_true_is_refused_in_production():
    from app.core.config import Settings

    try:
        Settings(
            _env_file=None, ENVIRONMENT="production", DEMO_MODE=True,
            DATABASE_URL="x", REDIS_URL="x", SUPABASE_URL="x", SUPABASE_ANON_KEY="x",
            SUPABASE_SERVICE_ROLE_KEY="x", JWT_SECRET="x",
        )
        assert False, "should have raised"
    except Exception as exc:
        assert "DEMO_MODE" in str(exc)


# ---- enabled (isolated demo-only app) --------------------------------


def test_demo_status_endpoint():
    with patch("app.api.demo.simulator.get_status", return_value={"running": False, "scenario": None, "trip_id": None, "tick": None, "total_ticks": None}):
        response = demo_client.get(f"{API}/demo/status")
    assert response.status_code == 200
    body = response.json()
    assert body["running"] is False
    assert set(body["available_scenarios"]) == {"normal", "falling_behind", "route_deviation", "sos", "completion"}


@patch("app.api.demo.get_group_members_with_profiles")
@patch("app.api.demo.demo_data.reset_demo_sync")
@patch("app.api.demo.simulator.stop_scenario", new_callable=AsyncMock)
@patch("app.api.demo.SessionLocal")
def test_reset_endpoint(mock_session_local, mock_stop, mock_reset, mock_members):
    from types import SimpleNamespace

    mock_session_local.return_value = SimpleNamespace(close=lambda: None)
    group_id = uuid.uuid4()
    mock_reset.return_value = SimpleNamespace(id=group_id)
    mock_members.return_value = [{}, {}, {}, {}]

    response = demo_client.post(f"{API}/demo/reset")

    assert response.status_code == 200
    body = response.json()
    assert body["group_id"] == str(group_id)
    assert body["member_count"] == 4
    mock_stop.assert_called_once()


@patch("app.api.demo.simulator.start_scenario", new_callable=AsyncMock)
def test_start_scenario_endpoint(mock_start):
    from app.demo.simulator import DemoRunState
    from datetime import datetime, timezone

    trip_id = uuid.uuid4()
    mock_start.return_value = DemoRunState(scenario="normal", trip_id=trip_id, started_at=datetime.now(timezone.utc), total_ticks=30)

    response = demo_client.post(f"{API}/demo/scenarios/normal/start")

    assert response.status_code == 200
    body = response.json()
    assert body["scenario"] == "normal"
    assert body["trip_id"] == str(trip_id)


@patch("app.api.demo.simulator.start_scenario", new_callable=AsyncMock)
def test_start_scenario_endpoint_rejects_unknown_scenario(mock_start):
    mock_start.side_effect = ValueError("Unknown demo scenario: 'bogus'.")
    response = demo_client.post(f"{API}/demo/scenarios/bogus/start")
    assert response.status_code == 400


@patch("app.api.demo.simulator.stop_scenario", new_callable=AsyncMock)
def test_stop_scenario_endpoint_rejects_unknown_scenario(mock_stop):
    response = demo_client.post(f"{API}/demo/scenarios/bogus/stop")
    assert response.status_code == 400
    mock_stop.assert_not_called()


@patch("app.api.demo.simulator.get_status")
@patch("app.api.demo.simulator.stop_scenario", new_callable=AsyncMock)
def test_stop_scenario_endpoint(mock_stop, mock_status):
    mock_status.return_value = {"running": False, "scenario": None, "trip_id": None, "tick": None, "total_ticks": None}
    response = demo_client.post(f"{API}/demo/scenarios/normal/stop")
    assert response.status_code == 200
    mock_stop.assert_called_once()
