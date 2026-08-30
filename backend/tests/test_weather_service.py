"""
app/weather/service.py: never raises regardless of provider/network
outcome, caches successful responses, and derives its transparent
warning rules deterministically. No real network calls — every HTTP path
is mocked (see the module docstring's "core system must work without
weather" rule, which this test suite exists to prove).
"""

from unittest.mock import AsyncMock, patch

import fakeredis
import pytest

from app.core.config import settings
from app.weather import service as weather_service
from app.weather.service import WeatherInfo, WeatherService, WeatherWarning, _derive_warnings


@pytest.fixture
def fake_redis():
    return fakeredis.FakeAsyncRedis(decode_responses=True)


# ---- warning derivation (pure) --------------------------------------------


def test_no_warnings_under_every_threshold():
    assert _derive_warnings(10.0, 2.0, 10000.0) == []


def test_heavy_rain_warning():
    warnings = _derive_warnings(80.0, 2.0, 10000.0)
    assert any(w.type == "HEAVY_RAIN" for w in warnings)


def test_high_wind_warning():
    warnings = _derive_warnings(10.0, 20.0, 10000.0)
    assert any(w.type == "HIGH_WIND" for w in warnings)


def test_low_visibility_warning():
    warnings = _derive_warnings(10.0, 2.0, 500.0)
    assert any(w.type == "LOW_VISIBILITY" for w in warnings)


def test_none_values_never_produce_a_warning():
    assert _derive_warnings(None, None, None) == []


# ---- missing configuration --------------------------------------------


async def test_openweathermap_without_api_key_is_unavailable(fake_redis, monkeypatch):
    monkeypatch.setattr(settings, "WEATHER_PROVIDER", "openweathermap")
    monkeypatch.setattr(settings, "WEATHER_API_KEY", None)
    result = await WeatherService.get_weather(fake_redis, 22.7, 75.8)
    assert result.weather_available is False


async def test_unknown_provider_is_unavailable(fake_redis, monkeypatch):
    monkeypatch.setattr(settings, "WEATHER_PROVIDER", "some-unsupported-provider")
    result = await WeatherService.get_weather(fake_redis, 22.7, 75.8)
    assert result.weather_available is False


# ---- provider failure never raises -----------------------------------------


async def test_get_weather_survives_an_exception_from_the_fetch_layer(fake_redis, monkeypatch):
    """Even if something below get_weather() raises unexpectedly (not
    just the documented "returns None on failure" contract each _fetch_*
    already follows internally), the public entry point itself must
    never propagate it — see the module docstring's "never raises"
    guarantee and get_weather()'s own outer try/except."""
    monkeypatch.setattr(settings, "WEATHER_PROVIDER", "open-meteo")

    with patch("app.weather.service._fetch_open_meteo", new_callable=AsyncMock, side_effect=ConnectionError("down")):
        result = await WeatherService.get_weather(fake_redis, 22.7, 75.8)

    assert result.weather_available is False


async def test_fetch_open_meteo_never_raises_on_http_error(fake_redis, monkeypatch):
    """The real (non-mocked) _fetch_open_meteo function, given a client
    that raises — proves its own internal try/except holds."""

    class _ExplodingClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return False

        async def get(self, *args, **kwargs):
            raise TimeoutError("simulated timeout")

    with patch("httpx.AsyncClient", return_value=_ExplodingClient()):
        result = await weather_service._fetch_open_meteo(22.7, 75.8)
    assert result is None  # never raises


async def test_get_weather_unavailable_when_fetch_returns_none(fake_redis, monkeypatch):
    monkeypatch.setattr(settings, "WEATHER_PROVIDER", "open-meteo")
    with patch("app.weather.service._fetch_open_meteo", new_callable=AsyncMock, return_value=None):
        result = await WeatherService.get_weather(fake_redis, 22.7, 75.8)
    assert result.weather_available is False


# ---- success + caching ---------------------------------------------------


async def test_successful_fetch_is_cached(fake_redis, monkeypatch):
    monkeypatch.setattr(settings, "WEATHER_PROVIDER", "open-meteo")
    fetched = WeatherInfo(weather_available=True, temperature_celsius=25.0, condition="CLEAR")

    with patch("app.weather.service._fetch_open_meteo", new_callable=AsyncMock, return_value=fetched) as mock_fetch:
        first = await WeatherService.get_weather(fake_redis, 22.70, 75.80)
        second = await WeatherService.get_weather(fake_redis, 22.70, 75.80)

    assert first.weather_available is True
    assert second.weather_available is True
    assert second.temperature_celsius == 25.0
    mock_fetch.assert_called_once()  # the second call was served from cache, not a second fetch


async def test_cache_respects_ttl_setting(fake_redis, monkeypatch):
    monkeypatch.setattr(settings, "WEATHER_PROVIDER", "open-meteo")
    monkeypatch.setattr(settings, "WEATHER_CACHE_TTL_SECONDS", 123)
    fetched = WeatherInfo(weather_available=True, temperature_celsius=10.0)

    with patch("app.weather.service._fetch_open_meteo", new_callable=AsyncMock, return_value=fetched):
        await WeatherService.get_weather(fake_redis, 22.70, 75.80)

    from app.core.redis_keys import weather_cache_key

    ttl = await fake_redis.ttl(weather_cache_key(22.70, 75.80))
    assert 0 < ttl <= 123


async def test_no_redis_still_fetches_without_caching(monkeypatch):
    monkeypatch.setattr(settings, "WEATHER_PROVIDER", "open-meteo")
    fetched = WeatherInfo(weather_available=True, temperature_celsius=18.0)
    with patch("app.weather.service._fetch_open_meteo", new_callable=AsyncMock, return_value=fetched):
        result = await WeatherService.get_weather(None, 22.7, 75.8)
    assert result.weather_available is True
    assert result.temperature_celsius == 18.0
