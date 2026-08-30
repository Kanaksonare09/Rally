import uuid
from typing import List, Optional

from pydantic import BaseModel


class DemoResetResponse(BaseModel):
    group_id: uuid.UUID
    member_count: int


class DemoScenarioResponse(BaseModel):
    scenario: str
    trip_id: uuid.UUID
    total_ticks: int


class DemoStatusResponse(BaseModel):
    running: bool
    scenario: Optional[str] = None
    trip_id: Optional[uuid.UUID] = None
    tick: Optional[int] = None
    total_ticks: Optional[int] = None
    available_scenarios: List[str]
