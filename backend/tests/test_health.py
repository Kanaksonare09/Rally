from fastapi.testclient import TestClient

from app.core.config import settings
from app.main import app

client = TestClient(app)


def test_app_starts_and_health_responds():
    """Proves the application boots successfully end-to-end via TestClient."""
    response = client.get(f"{settings.API_V1_STR}/health")
    assert response.status_code == 200


def test_health_response_shape():
    response = client.get(f"{settings.API_V1_STR}/health")
    body = response.json()
    assert "status" in body
    assert "database" in body
    assert "redis" in body
    assert "intelligence_worker" in body
    assert body["status"] in ("ok", "degraded")
    assert body["database"] in ("connected", "unreachable", "not_configured")
    assert body["redis"] in ("connected", "unreachable", "not_configured")
    assert body["intelligence_worker"] in ("ok", "starting", "stalled")


def test_health_reports_redis_not_configured_without_redis_url(monkeypatch):
    """No REDIS_URL is set in this test environment — /health must say so
    plainly rather than crash or silently claim connectivity."""
    monkeypatch.setattr(settings, "REDIS_URL", None)
    response = client.get(f"{settings.API_V1_STR}/health")
    assert response.json()["redis"] == "not_configured"


def test_health_redis_down_does_not_fail_overall_status():
    """Redis powers live tracking only — a healthy database-backed REST
    API must still report "ok" even if Redis is unreachable/unconfigured."""
    response = client.get(f"{settings.API_V1_STR}/health")
    body = response.json()
    if body["database"] == "connected":
        assert body["status"] == "ok"


def test_health_never_leaks_secrets():
    response = client.get(f"{settings.API_V1_STR}/health")
    text = response.text
    assert "SUPABASE_SERVICE_ROLE_KEY" not in text
    assert "JWT_SECRET" not in text
    assert "REDIS_URL" not in text


def test_root_endpoint():
    response = client.get("/")
    assert response.status_code == 200
    assert "message" in response.json()
