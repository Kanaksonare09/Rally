from typing import List

from pydantic import BaseModel


class RiskFactor(BaseModel):
    type: str
    impact: int
    description: str


class RiskScore(BaseModel):
    score: int
    level: str  # LOW | MEDIUM | HIGH | CRITICAL — see app/risk/service.py
    factors: List[RiskFactor]
