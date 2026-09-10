"""Integration tests for the /notifications router."""

import uuid
from collections.abc import Callable, Coroutine

import pytest
from httpx import AsyncClient
from sqlmodel.ext.asyncio.session import AsyncSession

from ai_shop_helper_backend.core.constants import NotificationType
from ai_shop_helper_backend.models.notifications import Notification
from ai_shop_helper_backend.models.roles import Role
from ai_shop_helper_backend.models.users import User


async def _create_org(client: AsyncClient, headers: dict[str, str]) -> uuid.UUID:
    """Create an org as the caller and return its id."""
    response = await client.post("/orgs/", headers=headers, json={"name": "Acme"})
    assert response.status_code == 201, response.text
    return uuid.UUID(response.json()["id"])


@pytest.fixture(autouse=True)
def _roles(seeded_roles: dict[str, Role]) -> None:
    """Ensure base roles exist for org-creation tests (org creation needs Owner)."""


async def _create_notification(
    session: AsyncSession,
    user_id: uuid.UUID,
    notification_type: str = NotificationType.EXECUTION_FINISHED,
    read: bool = False,
    org_id: uuid.UUID | None = None,
) -> Notification:
    from ai_shop_helper_backend.core.utils import get_datetime_utc

    notification = Notification(
        user_id=user_id,
        org_id=org_id,
        type=notification_type,
        payload={"reason": "test"},
        read_at=get_datetime_utc() if read else None,
    )
    session.add(notification)
    await session.commit()
    await session.refresh(notification)
    return notification


class TestGetUnreadCount:
    """Tests for the GET /notifications/unread-count endpoint."""

    async def test_counts_only_unread(
        self,
        client: AsyncClient,
        session: AsyncSession,
        create_user: Callable[..., Coroutine[None, None, User]],
        auth_headers: dict[str, str],
    ):
        """Test that unread-count only counts notifications without a read_at timestamp."""
        me_resp = await client.get("/users/me", headers=auth_headers)
        user_id = uuid.UUID(me_resp.json()["id"])
        await _create_notification(session, user_id)
        await _create_notification(session, user_id)
        await _create_notification(session, user_id, read=True)

        response = await client.get("/notifications/unread-count", headers=auth_headers)

        assert response.status_code == 200
        assert response.json()["unread_count"] == 2

    async def test_requires_auth(self, client: AsyncClient):
        """Test that unread-count requires authentication."""
        response = await client.get("/notifications/unread-count")
        assert response.status_code == 401

    async def test_filters_by_org(
        self,
        client: AsyncClient,
        session: AsyncSession,
        auth_headers: dict[str, str],
    ):
        """Test that org_id only counts unread notifications tied to that org."""
        me_resp = await client.get("/users/me", headers=auth_headers)
        user_id = uuid.UUID(me_resp.json()["id"])
        org_id = await _create_org(client, auth_headers)
        await _create_notification(session, user_id, org_id=org_id)
        await _create_notification(session, user_id)

        response = await client.get(
            f"/notifications/unread-count?org_id={org_id}", headers=auth_headers
        )

        assert response.status_code == 200
        assert response.json()["unread_count"] == 1


class TestGetNotifications:
    """Tests for the GET /notifications/ endpoint."""

    async def test_lists_only_own_notifications(
        self,
        client: AsyncClient,
        session: AsyncSession,
        create_user: Callable[..., Coroutine[None, None, User]],
        auth_headers: dict[str, str],
    ):
        """Test that a user only sees their own notifications."""
        me_resp = await client.get("/users/me", headers=auth_headers)
        user_id = uuid.UUID(me_resp.json()["id"])
        await _create_notification(session, user_id)
        other_user = await create_user(email="other@example.com")
        await _create_notification(session, other_user.id)

        response = await client.get("/notifications/", headers=auth_headers)

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 1

    async def test_filters_unread_only(
        self,
        client: AsyncClient,
        session: AsyncSession,
        create_user: Callable[..., Coroutine[None, None, User]],
        auth_headers: dict[str, str],
    ):
        """Test that unread_only=true excludes already-read notifications."""
        me_resp = await client.get("/users/me", headers=auth_headers)
        user_id = uuid.UUID(me_resp.json()["id"])
        await _create_notification(session, user_id, read=True)
        await _create_notification(session, user_id)

        response = await client.get(
            "/notifications/?unread_only=true", headers=auth_headers
        )

        assert response.status_code == 200
        assert response.json()["total"] == 1

    async def test_filters_by_org(
        self,
        client: AsyncClient,
        session: AsyncSession,
        auth_headers: dict[str, str],
    ):
        """Test that org_id only returns notifications tied to that org."""
        me_resp = await client.get("/users/me", headers=auth_headers)
        user_id = uuid.UUID(me_resp.json()["id"])
        org_id = await _create_org(client, auth_headers)
        await _create_notification(session, user_id, org_id=org_id)
        await _create_notification(session, user_id)

        response = await client.get(
            f"/notifications/?org_id={org_id}", headers=auth_headers
        )

        assert response.status_code == 200
        assert response.json()["total"] == 1


class TestMarkNotificationRead:
    """Tests for the PATCH /notifications/{notification_id}/read endpoint."""

    async def test_marks_own_notification_as_read(
        self,
        client: AsyncClient,
        session: AsyncSession,
        auth_headers: dict[str, str],
    ):
        """Test that a user can mark their own notification as read."""
        me_resp = await client.get("/users/me", headers=auth_headers)
        user_id = uuid.UUID(me_resp.json()["id"])
        notification = await _create_notification(session, user_id)

        response = await client.patch(
            f"/notifications/{notification.id}/read", headers=auth_headers
        )

        assert response.status_code == 200
        assert response.json()["read_at"] is not None

    async def test_cannot_mark_another_users_notification(
        self,
        client: AsyncClient,
        session: AsyncSession,
        create_user: Callable[..., Coroutine[None, None, User]],
        auth_headers: dict[str, str],
    ):
        """Test that marking another user's notification as read returns a 404."""
        other_user = await create_user(email="notmine@example.com")
        notification = await _create_notification(session, other_user.id)

        response = await client.patch(
            f"/notifications/{notification.id}/read", headers=auth_headers
        )

        assert response.status_code == 404

    async def test_not_found(self, client: AsyncClient, auth_headers: dict[str, str]):
        """Test that marking a non-existent notification as read returns a 404."""
        response = await client.patch(
            f"/notifications/{uuid.uuid4()}/read", headers=auth_headers
        )
        assert response.status_code == 404


class TestMarkNotificationUnread:
    """Tests for the PATCH /notifications/{notification_id}/unread endpoint."""

    async def test_marks_own_notification_as_unread(
        self,
        client: AsyncClient,
        session: AsyncSession,
        auth_headers: dict[str, str],
    ):
        """Test that a user can mark their own read notification as unread."""
        me_resp = await client.get("/users/me", headers=auth_headers)
        user_id = uuid.UUID(me_resp.json()["id"])
        notification = await _create_notification(session, user_id, read=True)

        response = await client.patch(
            f"/notifications/{notification.id}/unread", headers=auth_headers
        )

        assert response.status_code == 200
        assert response.json()["read_at"] is None

    async def test_cannot_mark_another_users_notification(
        self,
        client: AsyncClient,
        session: AsyncSession,
        create_user: Callable[..., Coroutine[None, None, User]],
        auth_headers: dict[str, str],
    ):
        """Test that marking another user's notification as unread returns a 404."""
        other_user = await create_user(email="notmine2@example.com")
        notification = await _create_notification(session, other_user.id, read=True)

        response = await client.patch(
            f"/notifications/{notification.id}/unread", headers=auth_headers
        )

        assert response.status_code == 404

    async def test_not_found(self, client: AsyncClient, auth_headers: dict[str, str]):
        """Test that marking a non-existent notification as unread returns a 404."""
        response = await client.patch(
            f"/notifications/{uuid.uuid4()}/unread", headers=auth_headers
        )
        assert response.status_code == 404


class TestMarkAllRead:
    """Tests for the PATCH /notifications/read-all endpoint."""

    async def test_marks_all_unread_as_read(
        self,
        client: AsyncClient,
        session: AsyncSession,
        auth_headers: dict[str, str],
    ):
        """Test that read-all marks every unread notification and reports the count."""
        me_resp = await client.get("/users/me", headers=auth_headers)
        user_id = uuid.UUID(me_resp.json()["id"])
        await _create_notification(session, user_id)
        await _create_notification(session, user_id)
        await _create_notification(session, user_id, read=True)

        response = await client.patch("/notifications/read-all", headers=auth_headers)

        assert response.status_code == 200
        assert response.json()["marked_count"] == 2

        unread_resp = await client.get(
            "/notifications/unread-count", headers=auth_headers
        )
        assert unread_resp.json()["unread_count"] == 0

    async def test_does_not_touch_other_users_notifications(
        self,
        client: AsyncClient,
        session: AsyncSession,
        create_user: Callable[..., Coroutine[None, None, User]],
        auth_headers: dict[str, str],
    ):
        """Test that read-all only marks the current user's own notifications."""
        other_user = await create_user(email="not-mine-readall@example.com")
        await _create_notification(session, other_user.id)

        response = await client.patch("/notifications/read-all", headers=auth_headers)

        assert response.status_code == 200
        assert response.json()["marked_count"] == 0

    async def test_scopes_by_org(
        self,
        client: AsyncClient,
        session: AsyncSession,
        auth_headers: dict[str, str],
    ):
        """Test that org_id only marks unread notifications tied to that org as read."""
        me_resp = await client.get("/users/me", headers=auth_headers)
        user_id = uuid.UUID(me_resp.json()["id"])
        org_id = await _create_org(client, auth_headers)
        await _create_notification(session, user_id, org_id=org_id)
        await _create_notification(session, user_id)

        response = await client.patch(
            f"/notifications/read-all?org_id={org_id}", headers=auth_headers
        )

        assert response.status_code == 200
        assert response.json()["marked_count"] == 1

        unread_resp = await client.get(
            "/notifications/unread-count", headers=auth_headers
        )
        assert unread_resp.json()["unread_count"] == 1


class TestNotificationPreferences:
    """Tests for the GET/PATCH /notifications/preferences endpoints."""

    async def test_defaults_to_unmuted(
        self, client: AsyncClient, auth_headers: dict[str, str]
    ):
        """Test that all mutable notification types default to unmuted."""
        response = await client.get("/notifications/preferences", headers=auth_headers)

        assert response.status_code == 200
        preferences = response.json()["preferences"]
        assert all(muted is False for muted in preferences.values())
        assert NotificationType.BILLING not in preferences

    async def test_can_mute_a_mutable_type(
        self, client: AsyncClient, auth_headers: dict[str, str]
    ):
        """Test that a user can mute a mutable notification type."""
        response = await client.patch(
            "/notifications/preferences",
            headers=auth_headers,
            json={
                "notification_type": NotificationType.EXECUTION_FINISHED,
                "muted": True,
            },
        )

        assert response.status_code == 200
        assert (
            response.json()["preferences"][NotificationType.EXECUTION_FINISHED] is True
        )

    async def test_cannot_mute_mandatory_type(
        self, client: AsyncClient, auth_headers: dict[str, str]
    ):
        """Test that muting a non-mutable type (e.g. BILLING) is rejected."""
        response = await client.patch(
            "/notifications/preferences",
            headers=auth_headers,
            json={"notification_type": NotificationType.BILLING, "muted": True},
        )

        assert response.status_code == 400
