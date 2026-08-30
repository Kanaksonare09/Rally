"""
Endpoint-level tests for app/api/notifications.py: authentication, and
that the user id driving every query always comes from the verified JWT
— never a query/body parameter — so there is no way to read or modify
another user's notifications.
"""

import uuid
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from app.core.config import settings
from app.core.database import get_db
from app.main import app
from app.models.notification import Notification
from tests.conftest import DEFAULT_TEST_USER_ID, make_token

client = TestClient(app)
API = settings.API_V1_STR
USER_ID = uuid.UUID(DEFAULT_TEST_USER_ID)


def _auth_headers():
    return {"Authorization": f"Bearer {make_token(sub=DEFAULT_TEST_USER_ID)}"}


def make_notification(**overrides) -> Notification:
    n = Notification(
        id=uuid.uuid4(), user_id=USER_ID, trip_id=uuid.uuid4(), type="TRIP_STARTED",
        title="Trip started", message="Go!", severity="INFO", dedup_key=None,
        notification_metadata={}, read_at=None, created_at=datetime.now(timezone.utc),
    )
    for k, v in overrides.items():
        setattr(n, k, v)
    return n


# ---- authentication ---------------------------------------------------


def test_unauthenticated_cannot_list_notifications():
    assert client.get(f"{API}/notifications").status_code == 401


def test_unauthenticated_cannot_read_unread_count():
    assert client.get(f"{API}/notifications/unread-count").status_code == 401


def test_unauthenticated_cannot_mark_read():
    assert client.patch(f"{API}/notifications/{uuid.uuid4()}/read").status_code == 401


def test_unauthenticated_cannot_mark_all_read():
    assert client.patch(f"{API}/notifications/read-all").status_code == 401


# ---- list / unread-count -------------------------------------------------


@patch("app.api.notifications.notification_service.get_unread_count")
@patch("app.api.notifications.notification_service.count_notifications")
@patch("app.api.notifications.notification_service.list_notifications")
def test_list_notifications_returns_own_only(mock_list, mock_count, mock_unread):
    app.dependency_overrides[get_db] = lambda: MagicMock()
    mock_list.return_value = [make_notification()]
    mock_count.return_value = 1
    mock_unread.return_value = 1
    try:
        response = client.get(f"{API}/notifications", headers=_auth_headers())
    finally:
        app.dependency_overrides.pop(get_db, None)

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 1
    assert body["unread_count"] == 1
    # The user id passed to the service is always the verified caller —
    # never anything from the request itself (there's no user_id param).
    called_user_id = mock_list.call_args.args[1]
    assert called_user_id == USER_ID


@patch("app.api.notifications.notification_service.get_unread_count")
def test_unread_count_endpoint(mock_unread):
    app.dependency_overrides[get_db] = lambda: MagicMock()
    mock_unread.return_value = 5
    try:
        response = client.get(f"{API}/notifications/unread-count", headers=_auth_headers())
    finally:
        app.dependency_overrides.pop(get_db, None)

    assert response.status_code == 200
    assert response.json()["unread_count"] == 5


def test_pagination_limit_enforced():
    app.dependency_overrides[get_db] = lambda: MagicMock()
    try:
        response = client.get(f"{API}/notifications?limit=99999", headers=_auth_headers())
    finally:
        app.dependency_overrides.pop(get_db, None)
    assert response.status_code == 422


# ---- mark read / read-all ------------------------------------------------


@patch("app.api.notifications.notification_service.mark_read")
@patch("app.api.notifications.notification_service.get_notification_for_user")
def test_mark_read_scoped_to_caller(mock_get, mock_mark):
    app.dependency_overrides[get_db] = lambda: MagicMock()
    notification = make_notification()
    mock_get.return_value = notification
    mock_mark.return_value = make_notification(read_at=datetime.now(timezone.utc))
    try:
        response = client.patch(f"{API}/notifications/{notification.id}/read", headers=_auth_headers())
    finally:
        app.dependency_overrides.pop(get_db, None)

    assert response.status_code == 200
    called_user_id = mock_get.call_args.args[2]
    assert called_user_id == USER_ID


@patch("app.api.notifications.notification_service.get_notification_for_user")
def test_mark_read_for_someone_elses_notification_is_404(mock_get):
    from app.core.errors import AppHTTPException

    app.dependency_overrides[get_db] = lambda: MagicMock()
    mock_get.side_effect = AppHTTPException(status_code=404, code="NOTIFICATION_NOT_FOUND", detail="Notification not found.")
    try:
        response = client.patch(f"{API}/notifications/{uuid.uuid4()}/read", headers=_auth_headers())
    finally:
        app.dependency_overrides.pop(get_db, None)

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "NOTIFICATION_NOT_FOUND"


@patch("app.api.notifications.notification_service.mark_all_read")
def test_mark_all_read_scoped_to_caller(mock_mark_all):
    app.dependency_overrides[get_db] = lambda: MagicMock()
    mock_mark_all.return_value = 3
    try:
        response = client.patch(f"{API}/notifications/read-all", headers=_auth_headers())
    finally:
        app.dependency_overrides.pop(get_db, None)

    assert response.status_code == 200
    assert response.json()["marked_count"] == 3
    called_user_id = mock_mark_all.call_args.args[1]
    assert called_user_id == USER_ID


# ---- regression --------------------------------------------------------


def test_health_endpoint_still_works():
    response = client.get(f"{API}/health")
    assert response.status_code == 200
