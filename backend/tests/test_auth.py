from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from app.core.config import settings
from app.dependencies.auth import get_current_profile
from app.main import app
from tests.conftest import DEFAULT_TEST_USER_ID, make_token

client = TestClient(app)
ME_URL = f"{settings.API_V1_STR}/auth/me"


@pytest.fixture
def fake_profile_override():
    """/auth/me also depends on get_current_profile, which needs a real DB
    session — there's none available here, so we override just that one
    dependency with an in-memory fake. get_current_user (the actual JWT
    verification) is deliberately left un-mocked in every test below."""
    fake_profile = SimpleNamespace(full_name="Test User", avatar_url=None)
    app.dependency_overrides[get_current_profile] = lambda: fake_profile
    yield fake_profile
    app.dependency_overrides.pop(get_current_profile, None)


def test_me_without_token_returns_401():
    response = client.get(ME_URL)
    assert response.status_code == 401
    body = response.json()
    assert body["success"] is False
    assert body["error"]["code"] == "UNAUTHORIZED"


def test_me_with_malformed_header_returns_401():
    # Wrong scheme entirely — HTTPBearer won't populate credentials at all.
    response = client.get(ME_URL, headers={"Authorization": "Basic dXNlcjpwYXNz"})
    assert response.status_code == 401


def test_me_with_empty_bearer_token_returns_401():
    response = client.get(ME_URL, headers={"Authorization": "Bearer "})
    assert response.status_code == 401


def test_me_with_invalid_jwt_returns_401():
    response = client.get(ME_URL, headers={"Authorization": "Bearer not-a-real-jwt"})
    assert response.status_code == 401


def test_me_with_expired_jwt_returns_401():
    token = make_token(expires_in_seconds=-60)
    response = client.get(ME_URL, headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 401


def test_me_with_wrong_signature_returns_401():
    token = make_token(secret="not-the-configured-secret")
    response = client.get(ME_URL, headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 401


def test_401_body_never_leaks_token_details():
    token = make_token(expires_in_seconds=-60)
    response = client.get(ME_URL, headers={"Authorization": f"Bearer {token}"})
    text = response.text
    assert token not in text
    if settings.JWT_SECRET:
        assert settings.JWT_SECRET not in text


def test_me_with_valid_token_returns_200(fake_profile_override):
    token = make_token(sub=DEFAULT_TEST_USER_ID, email="demo@rally.app")
    response = client.get(ME_URL, headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 200
    body = response.json()
    assert body["id"] == DEFAULT_TEST_USER_ID
    assert body["email"] == "demo@rally.app"
    assert body["profile"]["full_name"] == "Test User"


def test_me_id_always_comes_from_verified_token_not_client_input(fake_profile_override):
    """A client cannot claim to be a different user via query params, a
    body, or any other request field — the id is only ever the JWT sub."""
    token = make_token(sub=DEFAULT_TEST_USER_ID)
    response = client.request(
        "GET",
        f"{ME_URL}?user_id=attacker-controlled-id",
        headers={"Authorization": f"Bearer {token}"},
        json={"id": "attacker-controlled-id", "user_id": "attacker-controlled-id"},
    )

    assert response.status_code == 200
    assert response.json()["id"] == DEFAULT_TEST_USER_ID


def test_me_response_never_includes_service_role_key(fake_profile_override):
    token = make_token()
    response = client.get(ME_URL, headers={"Authorization": f"Bearer {token}"})
    text = response.text
    assert "SUPABASE_SERVICE_ROLE_KEY" not in text
    assert "service_role" not in text.lower()


def test_health_endpoint_still_works():
    response = client.get(f"{settings.API_V1_STR}/health")
    assert response.status_code == 200
