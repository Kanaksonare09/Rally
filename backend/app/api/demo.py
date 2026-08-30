"""
Demo control API — only ever registered on the app when DEMO_MODE=true
(see app/main.py); every route here operates exclusively on the one
fixed demo group/trip (app/demo/data.py's DEMO_GROUP_ID and whatever demo
trip currently belongs to it) and accepts no group_id/trip_id/user_id
from the caller at all, so there is no arbitrary id a request could
substitute to reach real production data even if this router were
somehow reachable. Not authenticated by its own dependency the way every
other endpoint in this backend is — see the README's Demo mode section
for why that's an accepted, deliberate scope for a hackathon control
surface that's already fully gated behind DEMO_MODE and refused
together with ENVIRONMENT=production at startup.
"""

import logging

from fastapi import APIRouter, HTTPException

from app.core.database import SessionLocal
from app.demo import data as demo_data
from app.demo import simulator
from app.schemas.demo import DemoResetResponse, DemoScenarioResponse, DemoStatusResponse
from app.services.group_service import get_group_members_with_profiles

logger = logging.getLogger("rally.demo")

router = APIRouter(prefix="/demo", tags=["Demo"])


@router.post("/reset", response_model=DemoResetResponse)
async def reset_demo_endpoint():
    await simulator.stop_scenario()
    if SessionLocal is None:
        raise HTTPException(status_code=503, detail="Database is not configured.")
    db = SessionLocal()
    try:
        group = demo_data.reset_demo_sync(db)
        members = get_group_members_with_profiles(db, group.id)
    finally:
        db.close()
    return DemoResetResponse(group_id=group.id, member_count=len(members))


@router.post("/scenarios/{scenario}/start", response_model=DemoScenarioResponse)
async def start_scenario_endpoint(scenario: str):
    try:
        run = await simulator.start_scenario(scenario)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return DemoScenarioResponse(scenario=run.scenario, trip_id=run.trip_id, total_ticks=run.total_ticks)


@router.post("/scenarios/{scenario}/stop", response_model=DemoStatusResponse)
async def stop_scenario_endpoint(scenario: str):
    if scenario not in simulator.SCENARIOS:
        raise HTTPException(status_code=400, detail=f"Unknown demo scenario: {scenario!r}.")
    await simulator.stop_scenario()
    return DemoStatusResponse(**simulator.get_status(), available_scenarios=list(simulator.SCENARIOS))


@router.get("/status", response_model=DemoStatusResponse)
def get_demo_status_endpoint():
    return DemoStatusResponse(**simulator.get_status(), available_scenarios=list(simulator.SCENARIOS))
