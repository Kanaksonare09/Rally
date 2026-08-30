"""
DemoSimulator: deterministic GPS scenario playback for the demo group,
fed through the REAL ingestion pipeline (location_service.record_location,
live_state_service, presence_service) — never a shortcut that fabricates
analytics/alerts directly. The already-running intelligence worker
(app.intelligence.worker, started from app.main's lifespan) picks up
these GPS points on its own normal schedule and reacts exactly as it
would to genuine live tracking; this module never calls into the
intelligence/alert engines itself.

Deterministic, not random: every scenario is a fixed, precomputed
sequence of (user, tick) -> (lat, lon, speed) frames — the same scenario
name always produces the same sequence, tick-for-tick, run after run
(see _generate_frames()).
"""

import asyncio
import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, List, Optional

from starlette.concurrency import run_in_threadpool

from app.analytics.snapshot import generate_snapshot_safely
from app.core.config import settings
from app.core.database import SessionLocal
from app.core.redis import get_redis
from app.demo import data as demo_data
from app.demo.data import DEMO_USER_IDS
from app.models.enums import TripStatus
from app.models.trip import Trip
from app.route import service as route_service
from app.route.matcher import RouteGeometry, build_route_geometry
from app.schemas.location import LocationCreate
from app.schemas.sos import SOSCreate
from app.services import live_state_service, location_service, presence_service, trip_service
from app.sos import service as sos_service

logger = logging.getLogger("rally.demo")

SCENARIOS = ("normal", "falling_behind", "route_deviation", "sos", "completion")
_TICKS = 30
_SOS_TICK = 10
_DEVIATION_START_TICK = 10
_DEVIATION_END_TICK = 18
_DEVIATION_OFFSET_METERS = 250.0
_METERS_PER_DEGREE_LATITUDE = 111_320.0


def _interpolate(geometry: RouteGeometry, fraction: float) -> tuple:
    """A point `fraction` of the way along the route's real (Haversine)
    distance — walks the same coordinates/cumulative-distance table
    app/route/matcher.py builds, so this stays consistent with how live
    tracking measures progress along the same route."""
    fraction = max(0.0, min(1.0, fraction))
    target = fraction * geometry.total_distance_meters
    coords = geometry.coordinates
    cumulative = geometry.cumulative_distances_meters

    for i in range(len(coords) - 1):
        if cumulative[i] <= target <= cumulative[i + 1]:
            segment_len = cumulative[i + 1] - cumulative[i]
            local_fraction = 0.0 if segment_len == 0 else (target - cumulative[i]) / segment_len
            lon1, lat1 = coords[i]
            lon2, lat2 = coords[i + 1]
            return lat1 + (lat2 - lat1) * local_fraction, lon1 + (lon2 - lon1) * local_fraction

    lon, lat = coords[-1]
    return lat, lon


def _offset_north(lat: float, lon: float, meters: float) -> tuple:
    """A crude, deliberately simple lateral offset for the route-deviation
    scenario — not a real bearing-aware perpendicular offset, just enough
    to reliably push a point past OFF_ROUTE_THRESHOLD_METERS."""
    return lat + (meters / _METERS_PER_DEGREE_LATITUDE), lon


def _generate_frames(scenario: str, geometry: RouteGeometry) -> List[Dict[uuid.UUID, dict]]:
    """One dict per tick, `{user_id: {"latitude", "longitude", "speed"}}`
    for all 4 demo members — pure and deterministic, no I/O, so this is
    directly unit-testable without a database or Redis."""
    frames: List[Dict[uuid.UUID, dict]] = []
    for tick in range(_TICKS + 1):
        base_fraction = tick / _TICKS
        frame: Dict[uuid.UUID, dict] = {}
        for idx, user_id in enumerate(DEMO_USER_IDS):
            fraction = base_fraction
            speed = 8.0

            if scenario == "falling_behind" and idx == 3:
                fraction = base_fraction * 0.4
                speed = 2.0

            lat, lon = _interpolate(geometry, fraction)

            if scenario == "route_deviation" and idx == 3 and _DEVIATION_START_TICK <= tick <= _DEVIATION_END_TICK:
                lat, lon = _offset_north(lat, lon, _DEVIATION_OFFSET_METERS)

            frame[user_id] = {"latitude": lat, "longitude": lon, "speed": speed}
        frames.append(frame)
    return frames


@dataclass
class DemoRunState:
    scenario: str
    trip_id: uuid.UUID
    started_at: datetime
    total_ticks: int
    current_tick: int = 0
    task: Optional[asyncio.Task] = field(default=None, repr=False)


_current_run: Optional[DemoRunState] = None


def get_status() -> dict:
    if _current_run is None:
        return {"running": False, "scenario": None, "trip_id": None, "tick": None, "total_ticks": None}
    return {
        "running": True, "scenario": _current_run.scenario, "trip_id": str(_current_run.trip_id),
        "tick": _current_run.current_tick, "total_ticks": _current_run.total_ticks,
    }


async def stop_scenario() -> None:
    global _current_run
    if _current_run is None or _current_run.task is None:
        _current_run = None
        return
    task = _current_run.task
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass
    _current_run = None


async def start_scenario(scenario: str) -> DemoRunState:
    global _current_run
    if scenario not in SCENARIOS:
        raise ValueError(f"Unknown demo scenario: {scenario!r}. Valid scenarios: {', '.join(SCENARIOS)}")
    if _current_run is not None:
        await stop_scenario()
    if SessionLocal is None:
        raise RuntimeError("Database is not configured.")

    db = SessionLocal()
    try:
        trip = await run_in_threadpool(demo_data.create_and_start_demo_trip_sync, db)
        route = await run_in_threadpool(route_service.get_route_by_trip, db, trip.id)
    finally:
        db.close()

    geometry = build_route_geometry(route.coordinates)
    total_ticks = _TICKS

    _current_run = DemoRunState(
        scenario=scenario, trip_id=trip.id, started_at=datetime.now(timezone.utc), total_ticks=total_ticks
    )
    _current_run.task = asyncio.create_task(_run_scenario(scenario, trip.id, geometry))
    logger.info("Demo scenario started: scenario=%s trip_id=%s", scenario, trip.id)
    return _current_run


def _record_tick_sync(db, trip_id: uuid.UUID, user_id: uuid.UUID, state: dict) -> None:
    trip = db.get(Trip, trip_id)
    if trip is None or trip.status != TripStatus.ACTIVE:
        return
    data = LocationCreate(latitude=state["latitude"], longitude=state["longitude"], accuracy=5.0, speed=state["speed"], heading=None)
    location_service.record_location(db, trip, user_id, data)


def _trigger_sos_sync(db, trip_id: uuid.UUID):
    return db.get(Trip, trip_id)


async def _run_scenario(scenario: str, trip_id: uuid.UUID, geometry: RouteGeometry) -> None:
    global _current_run
    frames = _generate_frames(scenario, geometry)
    try:
        redis = get_redis()
    except RuntimeError:
        redis = None

    try:
        for tick, frame in enumerate(frames):
            if _current_run is not None:
                _current_run.current_tick = tick

            if SessionLocal is None:
                return
            db = SessionLocal()
            try:
                for user_id, state in frame.items():
                    await run_in_threadpool(_record_tick_sync, db, trip_id, user_id, state)
                    if redis is not None:
                        now_iso = datetime.now(timezone.utc).isoformat()
                        await live_state_service.set_live_location(
                            redis, trip_id, user_id, latitude=state["latitude"], longitude=state["longitude"],
                            accuracy=5.0, speed=state["speed"], heading=None, recorded_at=now_iso, updated_at=now_iso,
                        )
                        await presence_service.mark_online(redis, trip_id, user_id)

                if scenario == "sos" and tick == _SOS_TICK:
                    sos_user = DEMO_USER_IDS[3]
                    trip = await run_in_threadpool(_trigger_sos_sync, db, trip_id)
                    if trip is not None:
                        sos_state = frame[sos_user]
                        await sos_service.trigger_sos(
                            db, redis, trip_id, trip.group_id, sos_user,
                            SOSCreate(latitude=sos_state["latitude"], longitude=sos_state["longitude"], message="Demo SOS scenario"),
                        )
            finally:
                db.close()

            await asyncio.sleep(settings.DEMO_TICK_INTERVAL_SECONDS)

        if scenario == "completion":
            db = SessionLocal()
            try:
                trip = await run_in_threadpool(lambda: db.get(Trip, trip_id))
                if trip is not None and trip.status == TripStatus.ACTIVE:
                    updated = await run_in_threadpool(trip_service.end_trip, db, trip)
                    await run_in_threadpool(route_service.complete_route_sync, db, trip_id)
                    await run_in_threadpool(generate_snapshot_safely, db, updated)
            finally:
                db.close()

    except asyncio.CancelledError:
        raise
    except Exception:
        logger.exception("Demo scenario %s crashed mid-run (trip_id=%s)", scenario, trip_id)
    finally:
        if _current_run is not None and _current_run.trip_id == trip_id:
            _current_run = None
