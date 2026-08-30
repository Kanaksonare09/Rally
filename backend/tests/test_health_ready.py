"""
GET /health/ready — readiness, distinct from GET /health's liveness (see
tests/test_health.py for the existing liveness suite, unchanged by this
phase). Readiness must reflect a real dependency failure with a 503;
liveness never does.
"""

from fastapi.testclient import TestClient

from app.core.config import settings
from app.main import app

client = TestClient(app)
API = settings.API_V1_STR


def test_readiness_response_shape():
    response = client.get(f"{API}/health/ready")
    body = response.json()
    assert set(body.keys()) == {"status", "database", "redis"}
    assert body["status"] in ("ready", "not_ready")
    assert body["database"] in ("ok", "unavailable")
    assert body["redis"] in ("ok", "unavailable")


def test_readiness_is_not_ready_when_database_unavailable(monkeypatch):
    monkeypatch.setattr(settings, "DATABASE_URL", None)
    response = client.get(f"{API}/health/ready")
    assert response.status_code == 503
    body = response.json()
    assert body["status"] == "not_ready"
    assert body["database"] == "unavailable"


def test_readiness_ignores_redis_when_it_was_never_configured(monkeypatch):
    """A deployment that never set REDIS_URL is intentionally running
    without live tracking, not degraded — readiness must not fail it."""
    monkeypatch.setattr(settings, "REDIS_URL", None)
    monkeypatch.setattr("app.api.health.check_database_connection", lambda: True)
    monkeypatch.setattr(settings, "DATABASE_URL", "postgresql://irrelevant")
    response = client.get(f"{API}/health/ready")
    body = response.json()
    assert body["redis"] == "ok"


def test_readiness_is_not_ready_when_redis_configured_but_unreachable(monkeypatch):
    monkeypatch.setattr(settings, "REDIS_URL", "redis://unreachable:6379/0")
    monkeypatch.setattr("app.api.health.check_database_connection", lambda: True)
    monkeypatch.setattr(settings, "DATABASE_URL", "postgresql://irrelevant")

    async def _unreachable():
        return False

    monkeypatch.setattr("app.api.health.ping_redis", _unreachable)

    response = client.get(f"{API}/health/ready")
    assert response.status_code == 503
    assert response.json()["redis"] == "unavailable"


def test_readiness_never_leaks_secrets():
    response = client.get(f"{API}/health/ready")
    text = response.text
    assert "SUPABASE_SERVICE_ROLE_KEY" not in text
    assert "JWT_SECRET" not in text
    assert "DATABASE_URL" not in text


def test_liveness_still_returns_200_when_database_unavailable(monkeypatch):
    """The whole point of the liveness/readiness split — see the module
    docstring in app/api/health.py."""
    monkeypatch.setattr(settings, "DATABASE_URL", None)
    response = client.get(f"{API}/health")
    assert response.status_code == 200
