from fastapi import APIRouter, Response, status

from app.core.config import settings
from app.core.database import check_database_connection
from app.core.redis import ping_redis
from app.intelligence.worker import worker_health_status
from app.schemas.common import HealthResponse, ReadinessResponse

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    """Liveness: "is the process alive and able to respond at all?" —
    deliberately never gated on a dependency being reachable (Part 10:
    "Do not make liveness depend on PostgreSQL"). Redis/database/worker
    diagnostics are still reported here for convenience (this predates the
    Phase 11 readiness split and other code already depends on this
    shape), but a dependency being down never turns this into a non-200
    response — see GET /health/ready for the endpoint that's actually
    supposed to fail when a dependency is unavailable."""
    if not settings.DATABASE_URL:
        db_status = "not_configured"
    elif check_database_connection():
        db_status = "connected"
    else:
        db_status = "unreachable"

    if not settings.REDIS_URL:
        redis_status = "not_configured"
    elif await ping_redis():
        redis_status = "connected"
    else:
        redis_status = "unreachable"

    # Redis/the intelligence worker powering live tracking/detection is
    # never fatal to /health's overall "status" — REST APIs and
    # historical data work fine without them.
    return HealthResponse(
        status="ok" if db_status == "connected" else "degraded",
        database=db_status,
        redis=redis_status,
        intelligence_worker=worker_health_status(),
        version="0.1.0",
    )


@router.get("/health/ready", response_model=ReadinessResponse)
async def readiness(response: Response) -> ReadinessResponse:
    """Readiness: "can this instance currently serve real traffic?" —
    checks the dependencies that matter for that (PostgreSQL, Redis) and
    returns 503 the moment either critical one is down, so a load
    balancer / orchestrator stops routing traffic here until it recovers.
    Never confused with liveness (GET /health above): a instance that's
    alive-but-not-ready should be left running, just taken out of
    rotation — restarting it wouldn't fix a downstream Postgres/Redis
    outage."""
    database_ok = bool(settings.DATABASE_URL) and check_database_connection()
    # Redis is only critical to readiness when it's actually configured
    # for this deployment — a deployment that never set REDIS_URL is
    # intentionally running without live tracking, not degraded.
    redis_ok = (not settings.REDIS_URL) or await ping_redis()

    ready = database_ok and redis_ok
    response.status_code = status.HTTP_200_OK if ready else status.HTTP_503_SERVICE_UNAVAILABLE

    return ReadinessResponse(
        status="ready" if ready else "not_ready",
        database="ok" if database_ok else "unavailable",
        redis="ok" if redis_ok else "unavailable",
    )
