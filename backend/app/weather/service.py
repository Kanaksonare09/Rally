"""
WeatherService — optional, informational-only weather for a trip's
current location. Architecture rule (see the README's Weather section):
core tracking/intelligence/safety NEVER depends on this — every call site
wraps this in a try/except (or uses the already-safe `get_weather()`
below, which never raises) and treats `weather_available=False` as a
completely normal, expected outcome, not a degraded state.

Never called directly from a router — app/api/analytics.py's dashboard
endpoint is the one caller, going through this service exactly like every
other DashboardXService composed there.

Caching: Redis, keyed by a coarsened (~1km) coordinate bucket, TTL'd at
WEATHER_CACHE_TTL_SECONDS. Postgres never stores weather — there is no
"weather history" table; a trip only ever has "the weather at its current
location right now," not a stored past record (per this phase's "do not
store unnecessary weather history" instruction).
"""

import json
import logging
from dataclasses import dataclass, field
from typing import List, Optional

import httpx
from redis.asyncio import Redis

from app.core.config import settings
from app.core.redis_keys import weather_cache_key

logger = logging.getLogger("rally.weather")

# Deterministic, transparent warning thresholds — informational only,
# never "unsafe to travel." See the module docstring and the README's
# Weather safety section.
_HEAVY_RAIN_PRECIPITATION_PROBABILITY_PERCENT = 70.0
_HIGH_WIND_SPEED_MPS = 15.0  # ~54 km/h
_LOW_VISIBILITY_METERS = 1000.0


@dataclass(frozen=True)
class WeatherWarning:
    type: str
    severity: str
    reason: str


@dataclass(frozen=True)
class WeatherInfo:
    weather_available: bool
    temperature_celsius: Optional[float] = None
    condition: Optional[str] = None
    wind_speed_mps: Optional[float] = None
    precipitation_probability_percent: Optional[float] = None
    visibility_meters: Optional[float] = None
    warnings: List[WeatherWarning] = field(default_factory=list)


_UNAVAILABLE = WeatherInfo(weather_available=False)


def _bucket(value: float) -> float:
    """Rounds to ~2 decimal places (~1.1km at the equator) — fine
    precision for "what's the weather like around here," coarse enough
    that nearby members/trips share a cache entry."""
    return round(value, 2)


def _derive_warnings(precipitation_probability_percent: Optional[float], wind_speed_mps: Optional[float], visibility_meters: Optional[float]) -> List[WeatherWarning]:
    warnings: List[WeatherWarning] = []
    if precipitation_probability_percent is not None and precipitation_probability_percent >= _HEAVY_RAIN_PRECIPITATION_PROBABILITY_PERCENT:
        warnings.append(
            WeatherWarning(type="HEAVY_RAIN", severity="WARNING", reason="High precipitation probability.")
        )
    if wind_speed_mps is not None and wind_speed_mps >= _HIGH_WIND_SPEED_MPS:
        warnings.append(WeatherWarning(type="HIGH_WIND", severity="WARNING", reason="Sustained high wind speed."))
    if visibility_meters is not None and visibility_meters <= _LOW_VISIBILITY_METERS:
        warnings.append(WeatherWarning(type="LOW_VISIBILITY", severity="WARNING", reason="Reduced visibility conditions."))
    return warnings


async def _fetch_open_meteo(latitude: float, longitude: float) -> Optional[WeatherInfo]:
    """No API key required — https://open-meteo.com. Returns None (never
    raises) on any network/parsing failure."""
    url = "https://api.open-meteo.com/v1/forecast"
    params = {
        "latitude": latitude,
        "longitude": longitude,
        "current": "temperature_2m,wind_speed_10m,precipitation_probability,visibility,weather_code",
    }
    try:
        async with httpx.AsyncClient(timeout=settings.WEATHER_REQUEST_TIMEOUT_SECONDS) as client:
            response = await client.get(url, params=params)
        response.raise_for_status()
        data = response.json()
        current = data.get("current", {})
        precipitation = current.get("precipitation_probability")
        wind = current.get("wind_speed_10m")
        visibility = current.get("visibility")
        return WeatherInfo(
            weather_available=True,
            temperature_celsius=current.get("temperature_2m"),
            condition=_describe_weather_code(current.get("weather_code")),
            wind_speed_mps=wind,
            precipitation_probability_percent=precipitation,
            visibility_meters=visibility,
            warnings=_derive_warnings(precipitation, wind, visibility),
        )
    except Exception:
        logger.warning("Weather fetch (open-meteo) failed — continuing without weather data.", exc_info=True)
        return None


async def _fetch_openweathermap(latitude: float, longitude: float) -> Optional[WeatherInfo]:
    if not settings.WEATHER_API_KEY:
        return None
    url = "https://api.openweathermap.org/data/2.5/weather"
    params = {"lat": latitude, "lon": longitude, "appid": settings.WEATHER_API_KEY, "units": "metric"}
    try:
        async with httpx.AsyncClient(timeout=settings.WEATHER_REQUEST_TIMEOUT_SECONDS) as client:
            response = await client.get(url, params=params)
        response.raise_for_status()
        data = response.json()
        main = data.get("main", {})
        wind = data.get("wind", {}).get("speed")
        visibility = data.get("visibility")
        condition = (data.get("weather") or [{}])[0].get("main")
        # OpenWeatherMap's free tier has no direct precipitation *probability*
        # field on current weather — left None rather than approximated
        # from something else, per this phase's "no fake precision" rule.
        return WeatherInfo(
            weather_available=True,
            temperature_celsius=main.get("temp"),
            condition=condition,
            wind_speed_mps=wind,
            precipitation_probability_percent=None,
            visibility_meters=visibility,
            warnings=_derive_warnings(None, wind, visibility),
        )
    except Exception:
        logger.warning("Weather fetch (openweathermap) failed — continuing without weather data.", exc_info=True)
        return None


def _describe_weather_code(code: Optional[int]) -> Optional[str]:
    """Open-Meteo's WMO weather-code table, collapsed to a small human
    label set — not a precision forecast description."""
    if code is None:
        return None
    if code == 0:
        return "CLEAR"
    if code in (1, 2, 3):
        return "PARTLY_CLOUDY"
    if code in (45, 48):
        return "FOG"
    if 51 <= code <= 67:
        return "RAIN"
    if 71 <= code <= 86:
        return "SNOW"
    if code >= 95:
        return "THUNDERSTORM"
    return "UNKNOWN"


class WeatherService:
    @staticmethod
    async def get_weather(redis: Optional[Redis], latitude: float, longitude: float) -> WeatherInfo:
        """Never raises. `weather_available=False` covers: no provider
        configured, no API key when the provider needs one, a network
        failure, or a malformed response — the caller (the dashboard)
        treats all of these identically, exactly as required."""
        if settings.WEATHER_PROVIDER == "openweathermap" and not settings.WEATHER_API_KEY:
            return _UNAVAILABLE

        lat_bucket, lon_bucket = _bucket(latitude), _bucket(longitude)
        cache_key = weather_cache_key(lat_bucket, lon_bucket)

        if redis is not None:
            try:
                cached = await redis.get(cache_key)
                if cached is not None:
                    payload = json.loads(cached)
                    return WeatherInfo(
                        weather_available=True,
                        temperature_celsius=payload.get("temperature_celsius"),
                        condition=payload.get("condition"),
                        wind_speed_mps=payload.get("wind_speed_mps"),
                        precipitation_probability_percent=payload.get("precipitation_probability_percent"),
                        visibility_meters=payload.get("visibility_meters"),
                        warnings=[WeatherWarning(**w) for w in payload.get("warnings", [])],
                    )
            except Exception:
                logger.warning("Weather cache read failed — fetching fresh instead.", exc_info=True)

        try:
            if settings.WEATHER_PROVIDER == "openweathermap":
                result = await _fetch_openweathermap(latitude, longitude)
            elif settings.WEATHER_PROVIDER == "open-meteo":
                result = await _fetch_open_meteo(latitude, longitude)
            else:
                result = None
        except Exception:
            # Belt-and-suspenders: _fetch_* already catches every network/
            # parsing failure internally and returns None, but this outer
            # guard is what makes "weather can never break the rest of the
            # system" true even against a bug in that layer, not just the
            # failure modes it currently anticipates.
            logger.warning("Unexpected error fetching weather — continuing without it.", exc_info=True)
            result = None

        if result is None:
            return _UNAVAILABLE

        if redis is not None:
            try:
                await redis.set(
                    cache_key,
                    json.dumps(
                        {
                            "temperature_celsius": result.temperature_celsius,
                            "condition": result.condition,
                            "wind_speed_mps": result.wind_speed_mps,
                            "precipitation_probability_percent": result.precipitation_probability_percent,
                            "visibility_meters": result.visibility_meters,
                            "warnings": [w.__dict__ for w in result.warnings],
                        }
                    ),
                    ex=settings.WEATHER_CACHE_TTL_SECONDS,
                )
            except Exception:
                logger.warning("Weather cache write failed — continuing without caching this response.", exc_info=True)

        return result
