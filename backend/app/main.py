import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.auth import router as auth_router
from app.api.health import router as health_router
from app.core.config import settings
from app.core.errors import register_exception_handlers
from app.core.logging import configure_logging

configure_logging(settings.ENVIRONMENT)
logger = logging.getLogger("rally.startup")


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("%s starting up (environment=%s)", settings.PROJECT_NAME, settings.ENVIRONMENT)
    if not settings.DATABASE_URL:
        logger.warning("DATABASE_URL is not set - /health will report the database as not_configured.")
    yield


app = FastAPI(
    title=settings.PROJECT_NAME,
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

register_exception_handlers(app)

app.include_router(health_router, prefix=settings.API_V1_STR)
app.include_router(auth_router, prefix=settings.API_V1_STR)

from app.api.groups import router as groups_router
app.include_router(groups_router, prefix=f"{settings.API_V1_STR}/groups")

from app.api.trips import router as trips_router
app.include_router(trips_router, prefix=settings.API_V1_STR)

from app.api.locations import router as locations_router
app.include_router(locations_router, prefix=settings.API_V1_STR)


@app.get("/")
def root() -> dict:
    return {
        "message": "RALLY API",
        "docs": "/docs",
        "health": f"{settings.API_V1_STR}/health",
    }
