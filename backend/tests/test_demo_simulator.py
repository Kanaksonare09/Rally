"""
app/demo/simulator.py — the pure, deterministic parts (_interpolate,
_generate_frames) need no database/Redis and are tested directly;
start/stop/status are tested with the DB/Redis-touching internals
patched (create_and_start_demo_trip_sync, record_location, etc.), the
same patched-collaborator pattern used throughout this test suite.
"""

import asyncio
import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from app.demo import simulator
from app.demo.data import DEMO_USER_IDS
from app.route.matcher import build_route_geometry

GEOMETRY = build_route_geometry([[75.0, 22.0], [75.0, 22.01], [75.01, 22.02]])


# ---- pure functions ----------------------------------------------------


def test_interpolate_at_zero_is_the_first_coordinate():
    lat, lon = simulator._interpolate(GEOMETRY, 0.0)
    assert (lat, lon) == (22.0, 75.0)


def test_interpolate_at_one_is_the_last_coordinate():
    lat, lon = simulator._interpolate(GEOMETRY, 1.0)
    assert (lat, lon) == (22.02, 75.01)


def test_interpolate_clamps_out_of_range_fractions():
    below = simulator._interpolate(GEOMETRY, -5.0)
    above = simulator._interpolate(GEOMETRY, 5.0)
    assert below == simulator._interpolate(GEOMETRY, 0.0)
    assert above == simulator._interpolate(GEOMETRY, 1.0)


def test_generate_frames_is_deterministic():
    a = simulator._generate_frames("normal", GEOMETRY)
    b = simulator._generate_frames("normal", GEOMETRY)
    assert a == b


def test_normal_scenario_all_members_progress_together():
    frames = simulator._generate_frames("normal", GEOMETRY)
    last_frame = frames[-1]
    positions = {uid: (s["latitude"], s["longitude"]) for uid, s in last_frame.items()}
    # All 4 members reach (approximately) the same final position.
    values = list(positions.values())
    assert all(v == values[0] for v in values)


def test_falling_behind_scenario_one_member_lags():
    frames = simulator._generate_frames("falling_behind", GEOMETRY)
    last_frame = frames[-1]
    lagging_user = DEMO_USER_IDS[3]
    leading_user = DEMO_USER_IDS[0]
    # The lagging member's speed is lower and their final position hasn't
    # reached the route's end the way the others have.
    assert last_frame[lagging_user]["speed"] < last_frame[leading_user]["speed"]
    assert last_frame[lagging_user]["latitude"] != last_frame[leading_user]["latitude"] or \
        last_frame[lagging_user]["longitude"] != last_frame[leading_user]["longitude"]


def test_route_deviation_scenario_offsets_only_during_the_deviation_window():
    frames = simulator._generate_frames("route_deviation", GEOMETRY)
    deviating_user = DEMO_USER_IDS[3]
    before = frames[simulator._DEVIATION_START_TICK - 1][deviating_user]
    during = frames[simulator._DEVIATION_START_TICK][deviating_user]
    after = frames[simulator._DEVIATION_END_TICK + 1][deviating_user]

    on_route_before = simulator._interpolate(GEOMETRY, (simulator._DEVIATION_START_TICK - 1) / simulator._TICKS)
    on_route_after = simulator._interpolate(GEOMETRY, (simulator._DEVIATION_END_TICK + 1) / simulator._TICKS)

    assert (before["latitude"], before["longitude"]) == on_route_before
    assert during["latitude"] != simulator._interpolate(GEOMETRY, simulator._DEVIATION_START_TICK / simulator._TICKS)[0]
    assert (after["latitude"], after["longitude"]) == on_route_after


def test_unknown_scenario_produces_no_special_behavior_but_is_still_valid_frames():
    """_generate_frames itself doesn't validate scenario names — that's
    start_scenario()'s job (see test below) — but an unrecognized name
    degrades to the same as "normal" rather than crashing."""
    frames = simulator._generate_frames("not-a-real-scenario", GEOMETRY)
    assert len(frames) == simulator._TICKS + 1


# ---- start/stop/status --------------------------------------------------


@pytest.fixture(autouse=True)
def _reset_run_state():
    simulator._current_run = None
    yield
    simulator._current_run = None


def test_status_when_nothing_running():
    status = simulator.get_status()
    assert status["running"] is False
    assert status["scenario"] is None


async def test_start_scenario_rejects_unknown_name():
    with pytest.raises(ValueError):
        await simulator.start_scenario("not-a-real-scenario")


async def test_start_scenario_creates_trip_and_tracks_status(monkeypatch):
    trip_id = uuid.uuid4()
    route = SimpleNamespace(coordinates=[[75.0, 22.0], [75.0, 22.01]])
    fake_trip = SimpleNamespace(id=trip_id)

    with patch("app.demo.simulator.SessionLocal", return_value=SimpleNamespace(close=lambda: None)), \
         patch("app.demo.simulator.demo_data.create_and_start_demo_trip_sync", return_value=fake_trip), \
         patch("app.demo.simulator.route_service.get_route_by_trip", return_value=route), \
         patch("app.demo.simulator.get_redis", side_effect=RuntimeError("not configured")):
        run = await simulator.start_scenario("normal")

    assert run.scenario == "normal"
    assert run.trip_id == trip_id
    status = simulator.get_status()
    assert status["running"] is True
    assert status["scenario"] == "normal"

    await simulator.stop_scenario()
    assert simulator.get_status()["running"] is False


async def test_starting_a_new_scenario_stops_the_previous_one(monkeypatch):
    trip_id_1, trip_id_2 = uuid.uuid4(), uuid.uuid4()
    route = SimpleNamespace(coordinates=[[75.0, 22.0], [75.0, 22.01]])

    with patch("app.demo.simulator.SessionLocal", return_value=SimpleNamespace(close=lambda: None)), \
         patch("app.demo.simulator.route_service.get_route_by_trip", return_value=route), \
         patch("app.demo.simulator.get_redis", side_effect=RuntimeError("not configured")), \
         patch(
             "app.demo.simulator.demo_data.create_and_start_demo_trip_sync",
             side_effect=[SimpleNamespace(id=trip_id_1), SimpleNamespace(id=trip_id_2)],
         ):
        first = await simulator.start_scenario("normal")
        assert first.trip_id == trip_id_1
        second = await simulator.start_scenario("falling_behind")

    assert second.trip_id == trip_id_2
    assert simulator.get_status()["scenario"] == "falling_behind"
    await simulator.stop_scenario()
