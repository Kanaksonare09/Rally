import uuid
from types import SimpleNamespace
from unittest.mock import patch, MagicMock

import pytest
from fastapi.testclient import TestClient

from app.core.config import settings
from app.main import app
from app.models.enums import GroupStatus, MemberRole, MemberStatus
from app.dependencies.auth import get_current_profile
from tests.conftest import DEFAULT_TEST_USER_ID, make_token

from app.core.database import get_db

client = TestClient(app)
GROUPS_URL = f"{settings.API_V1_STR}/groups"


@pytest.fixture
def fake_profile_override():
    fake_profile = SimpleNamespace(id=uuid.UUID(DEFAULT_TEST_USER_ID), full_name="Test User", avatar_url=None)
    app.dependency_overrides[get_current_profile] = lambda: fake_profile
    app.dependency_overrides[get_db] = lambda: MagicMock()
    yield fake_profile
    app.dependency_overrides.pop(get_current_profile, None)
    app.dependency_overrides.pop(get_db, None)


def test_unauthenticated_user_cannot_create_group():
    response = client.post(GROUPS_URL, json={"name": "Test Group"})
    assert response.status_code == 401


@patch("app.api.groups.group_service.create_group")
def test_authenticated_user_can_create_group(mock_create, fake_profile_override):
    token = make_token(sub=DEFAULT_TEST_USER_ID)
    
    mock_group = MagicMock()
    mock_group.id = uuid.uuid4()
    mock_group.name = "Test Group"
    mock_group.join_code = "RALLY-12345"
    mock_group.leader_id = uuid.UUID(DEFAULT_TEST_USER_ID)
    mock_group.destination_name = None
    mock_group.status = GroupStatus.ACTIVE
    mock_group.created_at = "2026-08-25T00:00:00Z"
    mock_group.updated_at = "2026-08-25T00:00:00Z"
    
    mock_create.return_value = mock_group

    response = client.post(
        GROUPS_URL,
        headers={"Authorization": f"Bearer {token}"},
        json={"name": "Test Group"}
    )
    
    assert response.status_code == 201
    assert response.json()["name"] == "Test Group"
    assert response.json()["join_code"] == "RALLY-12345"


@patch("app.api.groups.group_service.join_group")
def test_user_can_join_group(mock_join, fake_profile_override):
    token = make_token(sub=DEFAULT_TEST_USER_ID)
    
    mock_group = MagicMock()
    mock_group.id = uuid.uuid4()
    mock_group.name = "Test Group"
    mock_group.join_code = "RALLY-12345"
    mock_group.leader_id = uuid.uuid4()
    mock_group.destination_name = None
    mock_group.status = GroupStatus.ACTIVE
    mock_group.created_at = "2026-08-25T00:00:00Z"
    mock_group.updated_at = "2026-08-25T00:00:00Z"
    
    mock_join.return_value = mock_group

    response = client.post(
        f"{GROUPS_URL}/join",
        headers={"Authorization": f"Bearer {token}"},
        json={"join_code": "RALLY-12345"}
    )
    
    assert response.status_code == 200
    assert response.json()["join_code"] == "RALLY-12345"
    
    
@patch("app.api.groups.group_service.get_group_members_with_profiles")
def test_member_can_view_group_members(mock_get_members, fake_profile_override):
    token = make_token(sub=DEFAULT_TEST_USER_ID)
    group_id = uuid.uuid4()
    
    from app.dependencies.group import require_group_member
    
    mock_member = MagicMock(user_id=uuid.UUID(DEFAULT_TEST_USER_ID), role=MemberRole.MEMBER)
    app.dependency_overrides[require_group_member] = lambda: mock_member
    
    mock_get_members.return_value = [
        {
            "user_id": uuid.UUID(DEFAULT_TEST_USER_ID),
            "name": "Test User",
            "avatar_url": None,
            "role": MemberRole.MEMBER,
            "status": MemberStatus.ACTIVE,
            "joined_at": "2026-08-25T00:00:00Z"
        }
    ]

    response = client.get(
        f"{GROUPS_URL}/{group_id}/members",
        headers={"Authorization": f"Bearer {token}"}
    )
    
    app.dependency_overrides.pop(require_group_member, None)
    
    assert response.status_code == 200
    assert len(response.json()) == 1
    assert response.json()[0]["name"] == "Test User"
