from typing import Literal

from pydantic import BaseModel


class HealthResponse(BaseModel):
    status: Literal["ok", "degraded"]
    database: Literal["connected", "unreachable", "not_configured"]
    # Redis being down is deliberately never fatal to /health's overall
    # "status" — REST APIs and historical data don't depend on it, only
    # live WebSocket tracking does. See app/api/health.py.
    redis: Literal["connected", "unreachable", "not_configured"]
    # Same reasoning: the intelligence worker being stalled degrades
    # detection freshness, not the REST API or historical data.
    intelligence_worker: Literal["ok", "starting", "stalled"]
    version: str


class ReadinessResponse(BaseModel):
    """GET /health/ready — distinct from HealthResponse (liveness, see
    app/api/health.py): "ok"/"unavailable" here reflects whether this
    dependency is actually blocking readiness right now, not merely
    whether it's configured at all."""

    status: Literal["ready", "not_ready"]
    database: Literal["ok", "unavailable"]
    redis: Literal["ok", "unavailable"]


class ErrorDetail(BaseModel):
    code: str
    message: str


class ErrorResponse(BaseModel):
    success: Literal[False] = False
    error: ErrorDetail
