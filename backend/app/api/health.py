from fastapi import APIRouter

from app.core.config import settings
from app.core.database import check_database_connection
from app.schemas.common import HealthResponse

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    if not settings.DATABASE_URL:
        db_status = "not_configured"
    elif check_database_connection():
        db_status = "connected"
    else:
        db_status = "unreachable"

    return HealthResponse(
        status="ok" if db_status == "connected" else "degraded",
        database=db_status,
        version="0.1.0",
    )
