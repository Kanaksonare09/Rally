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
    assert body["status"] in ("ok", "degraded")
    assert body["database"] in ("connected", "unreachable", "not_configured")


def test_health_never_leaks_secrets():
    response = client.get(f"{settings.API_V1_STR}/health")
    text = response.text
    assert "SUPABASE_SERVICE_ROLE_KEY" not in text
    assert "JWT_SECRET" not in text


def test_root_endpoint():
    response = client.get("/")
    assert response.status_code == 200
    assert "message" in response.json()
