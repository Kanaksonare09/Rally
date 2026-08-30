"""
Application configuration, loaded from environment variables (.env in local
dev, real environment variables in production). Never hardcode secrets here —
every sensitive value is Optional/required-with-no-default so a missing .env
fails loudly instead of silently falling back to a bogus value.
"""

from functools import lru_cache
from typing import List, Optional

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Recognized ENVIRONMENT values are "development" | "test" | "production"
# (see _validate_production_config below) — not enforced as a strict enum
# on the field itself: an unrecognized value is treated the same as
# "development" (permissive) rather than crashing startup over a typo;
# only ENVIRONMENT=="production" triggers the fail-fast required-secrets
# check below. Every one of these must be a real value (not None/empty)
# before the app is allowed to start with ENVIRONMENT=production.
_REQUIRED_IN_PRODUCTION = (
    "DATABASE_URL",
    "REDIS_URL",
    "SUPABASE_URL",
    "SUPABASE_ANON_KEY",
    "SUPABASE_SERVICE_ROLE_KEY",
    "JWT_SECRET",
)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # --- Application metadata ---
    PROJECT_NAME: str = "RALLY API"
    API_V1_STR: str = "/api/v1"
    # "development" | "test" | "production" — see _validate_production_config.
    ENVIRONMENT: str = "development"
    # Swagger/OpenAPI/ReDoc. Default on (this is a demo/hackathon backend);
    # set false in a real production deployment that shouldn't advertise
    # its own API surface publicly. See app/main.py.
    ENABLE_DOCS: bool = True
    LOG_LEVEL: str = "INFO"

    # --- Supabase ---
    SUPABASE_URL: Optional[str] = None
    SUPABASE_ANON_KEY: Optional[str] = None
    # Server-only. Never send this to the frontend or return it in a response.
    SUPABASE_SERVICE_ROLE_KEY: Optional[str] = None

    # --- Database (Supabase Postgres) ---
    DATABASE_URL: Optional[str] = None

    # --- Redis (live trip state — see app/core/redis.py) ---
    REDIS_URL: Optional[str] = None
    # How long a user's live location stays valid before it's considered
    # stale and expires out of Redis on its own. Historical data in
    # location_history is completely unaffected by this.
    LIVE_LOCATION_TTL_SECONDS: int = 60
    # Separate from location freshness — a user can be ONLINE (recent
    # heartbeat/message) without having sent a GPS point recently.
    PRESENCE_TTL_SECONDS: int = 60
    # Lightweight per-connection abuse guard, not a hard device-GPS-rate
    # ceiling — generous enough that normal tracking never trips it. Also
    # the effective value for LOCATION_MAX_UPDATES_PER_SECOND (Phase 11's
    # spec name for this same concept) — kept as one setting rather than
    # two that could silently drift apart; see the README's Rate limiting
    # section.
    MAX_LOCATION_UPDATES_PER_SECOND: float = 5.0
    # Reject a WebSocket text frame larger than this before even parsing it.
    # Also the effective value for WEBSOCKET_MAX_MESSAGE_SIZE.
    WS_MAX_MESSAGE_BYTES: int = 8192
    # General per-connection message rate across EVERY WebSocket message
    # type (heartbeat, location_update, ...) — distinct from and in
    # addition to MAX_LOCATION_UPDATES_PER_SECOND, which only bounds
    # location_update specifically. Guards against a client flooding with
    # any message type, not just GPS.
    WEBSOCKET_MESSAGES_PER_SECOND: float = 10.0
    # A connection this far past its rate limit in a row is disconnected
    # outright rather than merely throttled — see app/websocket/handlers.py.
    WEBSOCKET_FLOOD_DISCONNECT_THRESHOLD: int = 20
    # One real user opening far more live-tracking connections than any
    # legitimate multi-tab/multi-device use case needs.
    MAX_WS_CONNECTIONS_PER_USER: int = 5

    # --- Redis client resilience (see app/core/redis.py) ---
    REDIS_CONNECT_TIMEOUT_SECONDS: float = 5.0
    REDIS_SOCKET_TIMEOUT_SECONDS: float = 5.0
    # Bounds the exponential-backoff retry loop the Pub/Sub subscriber
    # (app/websocket/manager.py) uses after losing its connection — not a
    # generic "retry every Redis command" setting (redis-py's own
    # retry_on_timeout, enabled below, covers ordinary commands).
    REDIS_RETRY_LIMIT: int = 5
    REDIS_RETRY_MAX_BACKOFF_SECONDS: float = 30.0

    # --- Rate limiting (Redis-backed — see app/core/rate_limit.py) ---
    RATE_LIMIT_ENABLED: bool = True
    # Catch-all applied to every request by RequestIDMiddleware (see
    # app/core/middleware.py) — the specific limits below are stricter
    # overrides layered on top for endpoints that warrant it, not a
    # replacement for this general one.
    GENERAL_API_RATE_LIMIT_PER_MINUTE: int = 100
    # /auth/me and similar caller-identity endpoints.
    AUTH_RATE_LIMIT_PER_MINUTE: int = 10
    # POST /groups/join — the one endpoint where a client is guessing a
    # secret (the join code); see JOIN CODE PROTECTION in the README.
    JOIN_GROUP_RATE_LIMIT_PER_MINUTE: int = 10
    # Deliberately not "strict" in the sense of blocking real emergencies:
    # see the SOS idempotency check in app/sos/service.py, which is the
    # actual defense against accidental duplicate-trigger spam. This limit
    # only guards against distinct trigger/cancel/retrigger abuse loops.
    SOS_RATE_LIMIT_PER_MINUTE: int = 5

    # --- Database connection pool (see app/core/database.py) ---
    DATABASE_POOL_SIZE: int = 5
    DATABASE_MAX_OVERFLOW: int = 10
    DATABASE_POOL_TIMEOUT_SECONDS: int = 30
    # Recycle a pooled connection after this long — protects against a
    # managed Postgres provider (Supabase included) silently dropping
    # idle connections server-side before the pool notices.
    DATABASE_POOL_RECYCLE_SECONDS: int = 1800

    # --- Request body size (Part 2 — input validation) ---
    # Rejects a request outright (413) when its declared Content-Length
    # exceeds this — see app/core/middleware.py::MaxBodySizeMiddleware.
    # Every JSON body this API accepts (trip/route/alert/SOS payloads) is
    # tiny; 1MB is already generous headroom, not a real ceiling on
    # anything legitimate.
    MAX_REQUEST_BODY_BYTES: int = 1_000_000

    # --- Data retention (see the README's Data retention section) ---
    # Documented, NOT activated: no scheduled job reads this in this
    # phase. Set it and wire a cleanup job explicitly later if needed —
    # this phase deliberately does not delete anything automatically.
    LOCATION_RETENTION_DAYS: Optional[int] = None

    # --- Intelligence engine (see app/intelligence/) ---
    # Movement classification
    STOP_SPEED_MPS: float = 0.8
    STOP_DURATION_SECONDS: int = 120
    STALE_LOCATION_SECONDS: int = 60
    # Falling behind: one member drifting from the group's center
    FALLING_BEHIND_DISTANCE_METERS: float = 500.0
    FALLING_BEHIND_DURATION_SECONDS: int = 120
    # Group separation: the group itself splitting into clusters
    GROUP_SEPARATION_DISTANCE_METERS: float = 800.0
    GROUP_SEPARATION_DURATION_SECONDS: int = 120
    # Isolated member: farther from every other member than they are from
    # each other
    ISOLATED_MEMBER_DISTANCE_METERS: float = 1000.0
    ISOLATED_MEMBER_DURATION_SECONDS: int = 120
    # Speed anomaly
    MAX_REASONABLE_SPEED_MPS: float = 45.0  # ~162 km/h
    SPEED_ANOMALY_DURATION_SECONDS: int = 20
    # Moving together (positive group state)
    GROUP_COHESION_DISTANCE_METERS: float = 300.0
    # Ignore a GPS point for separation/isolation/center calculations if
    # its reported accuracy is worse than this (larger = less precise).
    MIN_USABLE_ACCURACY_METERS: float = 100.0
    # How often the background evaluator re-analyzes each active trip.
    INTELLIGENCE_EVALUATION_INTERVAL_SECONDS: float = 3.0

    # --- Route intelligence (see app/route/) ---
    # How far a route's declared origin/destination may sit from the
    # geometry's own first/last coordinate before creation is rejected —
    # routing geometry rarely begins/ends at an exact coordinate match.
    ROUTE_ENDPOINT_TOLERANCE_METERS: float = 200.0
    OFF_ROUTE_THRESHOLD_METERS: float = 100.0
    ROUTE_DEVIATION_DURATION_SECONDS: int = 60
    ARRIVAL_THRESHOLD_METERS: float = 50.0
    ARRIVAL_DURATION_SECONDS: int = 30
    # A member's live location older than this isn't used for route
    # progress/matching (same STALE concept as movement classification,
    # kept as its own knob since route progress can tolerate a different
    # freshness window than raw movement state).
    ROUTE_PROGRESS_STALE_SECONDS: int = 60
    # Baseline (non-traffic-aware) planned speed, derived from a route's
    # own distance/estimated_duration at creation time — this default is
    # only the fallback when a route has no estimated_duration_seconds.
    BASELINE_ROUTE_SPEED_MPS: float = 11.0  # ~40 km/h

    # --- Analytics (see app/analytics/) ---
    # A GPS-to-GPS segment implying a speed above this is treated as an
    # impossible jump (bad fix, teleport, corrupted point) and excluded
    # from distance-traveled calculations — never silently included, never
    # silently rewritten in location_history itself. Reuses the same
    # order of magnitude as MAX_REASONABLE_SPEED_MPS above but kept as its
    # own knob since analytics can tolerate a different sanity bound than
    # live anomaly detection.
    MAX_ANALYTICS_SPEED_MPS: float = 45.0  # ~162 km/h
    # Analytics distance calculations also drop any point whose reported
    # accuracy is worse than MIN_USABLE_ACCURACY_METERS above — deliberately
    # reusing that same intelligence-engine threshold rather than adding a
    # second, possibly-diverging accuracy constant for the same concept.
    # How long a completed trip's computed analytics may be cached in
    # Redis before recomputation — analytics for a COMPLETED trip are
    # immutable in practice (nothing about a finished trip's historical
    # tables changes), so this is a plain TTL, not an event-driven
    # invalidation. Never applies to an ACTIVE trip's dashboard.
    ANALYTICS_CACHE_TTL_SECONDS: int = 300

    # --- Trip replay (app/analytics/replay.py) ---
    # Sampling resolution bounds for GET /trips/{trip_id}/replay — the
    # request-level `interval_seconds` query param is clamped to this
    # range regardless of what's asked for.
    REPLAY_MIN_INTERVAL_SECONDS: int = 2
    REPLAY_MAX_INTERVAL_SECONDS: int = 300
    REPLAY_DEFAULT_INTERVAL_SECONDS: int = 10
    # Hard ceiling on the number of timeline frames a replay response can
    # ever contain, independent of interval_seconds — protects against a
    # very long trip still producing an enormous payload.
    REPLAY_MAX_FRAMES: int = 2000

    # --- Smart risk score (app/risk/) ---
    # Score bands (see the README's Risk score section) — upper bound of
    # each tier; must be strictly increasing. > RISK_HIGH_MAX is CRITICAL.
    RISK_LOW_MAX: int = 30
    RISK_MEDIUM_MAX: int = 60
    RISK_HIGH_MAX: int = 80
    # Per-factor point weights. Deliberately configurable (not hardcoded
    # in RiskService) so tuning the score doesn't require touching
    # calculation logic — see app/risk/service.py::RISK_WEIGHTS for how
    # these compose, and its docstring for why each one is what it is.
    RISK_WEIGHT_ACTIVE_SOS: int = 50
    RISK_WEIGHT_CRITICAL_ALERT: int = 30
    RISK_WEIGHT_GROUP_SEPARATION: int = 17
    RISK_WEIGHT_ISOLATED_MEMBER: int = 12
    RISK_WEIGHT_FALLING_BEHIND: int = 10
    RISK_WEIGHT_ROUTE_DEVIATION: int = 8
    RISK_WEIGHT_UNEXPECTED_STOP: int = 8
    RISK_WEIGHT_SPEED_ANOMALY: int = 8
    RISK_WEIGHT_LOW_ACTIVE_RATIO: int = 10
    # Below this fraction of the group currently ONLINE, the
    # LOW_ACTIVE_RATIO factor kicks in — only meaningful for a live
    # (ACTIVE) trip; never applied to a completed one.
    RISK_LOW_ACTIVE_RATIO_THRESHOLD: float = 0.5

    # --- Weather integration (app/weather/) ---
    # Unset by default: weather is fully optional and never required for
    # core tracking to work — see the README's Weather section. Providers
    # currently supported: "open-meteo" (free, no key required) and
    # "openweathermap" (needs WEATHER_API_KEY).
    WEATHER_PROVIDER: str = "open-meteo"
    WEATHER_API_KEY: Optional[str] = None
    WEATHER_CACHE_TTL_SECONDS: int = 900
    # Bounded so a slow/hanging third-party API can never stall a
    # dashboard request — see app/weather/service.py.
    WEATHER_REQUEST_TIMEOUT_SECONDS: float = 5.0

    # --- Demo mode (app/demo/) ---
    # Must default False and must NEVER be enabled automatically — see
    # the README's Demo mode section and the startup guard in app.main
    # that refuses to boot with DEMO_MODE=true and ENVIRONMENT=production
    # set at the same time.
    DEMO_MODE: bool = False
    # How often the background simulator advances a running scenario.
    DEMO_TICK_INTERVAL_SECONDS: float = 2.0

    # --- Auth ---
    # Supabase Auth's JWT signing secret. FastAPI only ever *verifies* tokens
    # issued by Supabase Auth — it never mints its own.
    JWT_SECRET: Optional[str] = None
    JWT_ALGORITHM: str = "HS256"

    # --- Routing engine (wired later) ---
    OSRM_URL: Optional[str] = None

    # --- CORS ---
    # Comma-separated list of allowed origins, e.g.
    # "http://localhost:3000,https://rally.app". CORS_ALLOWED_ORIGINS is
    # this phase's preferred name and wins when set; FRONTEND_URL is kept
    # as a fallback so nothing already deployed against it breaks.
    FRONTEND_URL: str = "http://localhost:3000"
    CORS_ALLOWED_ORIGINS: Optional[str] = None

    @property
    def cors_origins(self) -> List[str]:
        raw = self.CORS_ALLOWED_ORIGINS or self.FRONTEND_URL
        return [origin.strip() for origin in raw.split(",") if origin.strip()]

    @model_validator(mode="after")
    def _validate_production_config(self) -> "Settings":
        """Fail fast, with a clear error, rather than let the app start in
        a broken state (Phase 11 — see the README's Configuration section).
        Only enforced when ENVIRONMENT=="production"; development/test (and
        any unrecognized value, treated the same as development) are
        unaffected, exactly as every previous phase's test suite already
        relies on — this validator adds no new required values there."""
        if self.ENVIRONMENT == "production":
            missing = [name for name in _REQUIRED_IN_PRODUCTION if not getattr(self, name)]
            if missing:
                raise ValueError(
                    "Missing required production configuration: "
                    + ", ".join(missing)
                    + ". Set these environment variables before starting with ENVIRONMENT=production."
                )
            if self.DEMO_MODE:
                raise ValueError(
                    "DEMO_MODE=true is not allowed with ENVIRONMENT=production. Demo mode creates and "
                    "manipulates trip/GPS data through the real pipeline and must never run against a "
                    "production deployment."
                )
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
