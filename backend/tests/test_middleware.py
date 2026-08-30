"""
app/core/middleware.py: request-id generation/reuse, and the standard
security headers. End-to-end via TestClient — these are ASGI middleware,
easiest to prove correct by actually sending a request through the full
stack rather than unit-testing dispatch() in isolation.
"""

from fastapi.testclient import TestClient

from app.core.config import settings
from app.main import app

client = TestClient(app)
API = settings.API_V1_STR


def test_response_carries_a_request_id_header():
    response = client.get(f"{API}/health")
    assert "x-request-id" in response.headers
    assert len(response.headers["x-request-id"]) > 0


def test_two_requests_get_different_request_ids():
    a = client.get(f"{API}/health")
    b = client.get(f"{API}/health")
    assert a.headers["x-request-id"] != b.headers["x-request-id"]


def test_incoming_request_id_is_reused_when_well_formed():
    response = client.get(f"{API}/health", headers={"X-Request-ID": "my-own-id-123"})
    assert response.headers["x-request-id"] == "my-own-id-123"


def test_malformed_incoming_request_id_is_replaced():
    """A client-supplied request id with unsafe characters/length must
    never be echoed back or logged verbatim — see
    app/core/middleware.py::_is_safe_request_id."""
    response = client.get(f"{API}/health", headers={"X-Request-ID": "not safe! <script>"})
    assert response.headers["x-request-id"] != "not safe! <script>"
    assert len(response.headers["x-request-id"]) > 0


def test_error_response_body_includes_the_same_request_id_as_the_header():
    response = client.get(f"{API}/trips/00000000-0000-0000-0000-000000000000")
    assert response.status_code == 401  # unauthenticated
    body = response.json()
    assert body["error"]["request_id"] == response.headers["x-request-id"]


def test_security_headers_present_on_every_response():
    response = client.get(f"{API}/health")
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["x-frame-options"] == "DENY"
    assert "referrer-policy" in response.headers


def test_security_headers_present_on_error_responses_too():
    response = client.get(f"{API}/trips/00000000-0000-0000-0000-000000000000")
    assert response.status_code == 401
    assert response.headers["x-content-type-options"] == "nosniff"


def test_cors_headers_present_for_allowed_origin():
    response = client.get(f"{API}/health", headers={"Origin": "http://localhost:3000"})
    assert response.headers.get("access-control-allow-origin") == "http://localhost:3000"
