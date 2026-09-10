"""Unit tests for services/notifications.py — all DB calls mocked via mock_session."""

import uuid
from unittest.mock import AsyncMock, MagicMock

from ai_shop_helper_backend.core.constants import AccessLevel, NotificationType
from ai_shop_helper_backend.models.notifications import (
    Notification,
    NotificationPreference,
)
from ai_shop_helper_backend.services.notifications import (
    create_notification,
    get_notification_by_id,
    get_notifications,
    get_preferences,
    get_unread_count,
    mark_all_as_read,
    mark_as_read,
    mark_as_unread,
    notify_org_members_by_role,
    set_preference,
)


class TestCreateNotification:
    """Tests for the create_notification service function."""

    async def test_creates_and_adds_to_session(self, mock_session: AsyncMock):
        """Test that create_notification adds a Notification to the session when the type is unmuted."""
        mock_session.exec.return_value.first.return_value = None
        user_id = uuid.uuid4()

        result = await create_notification(
            mock_session,
            user_id,
            NotificationType.EXECUTION_FINISHED,
            payload={"reason": "success"},
        )

        mock_session.add.assert_called_once()
        assert result is not None
        assert result.user_id == user_id
        assert result.type == NotificationType.EXECUTION_FINISHED

    async def test_skips_creation_when_muted(self, mock_session: AsyncMock):
        """Test that create_notification returns None and does not touch the session when the type is muted."""
        mock_session.exec.return_value.first.return_value = True

        result = await create_notification(
            mock_session,
            uuid.uuid4(),
            NotificationType.EXECUTION_FINISHED,
            payload={"reason": "success"},
        )

        mock_session.add.assert_not_called()
        assert result is None

    async def test_mandatory_type_ignores_mute_check(self, mock_session: AsyncMock):
        """Test that a non-mutable type (e.g. BILLING) is always created without querying preferences."""
        result = await create_notification(
            mock_session,
            uuid.uuid4(),
            NotificationType.BILLING,
            payload={"reason": "credits_granted_topup", "credits": 100},
        )

        mock_session.exec.assert_not_called()
        mock_session.add.assert_called_once()
        assert result is not None


class TestNotifyOrgMembersByRole:
    """Tests for the notify_org_members_by_role service function."""

    async def test_creates_notification_for_each_qualifying_member(
        self, mock_session: AsyncMock
    ):
        """Test that a notification is created for every member whose access_level qualifies."""
        org_id = uuid.uuid4()
        user_ids = [uuid.uuid4(), uuid.uuid4()]

        members_result = MagicMock()
        members_result.all.return_value = user_ids
        preference_result = MagicMock()
        preference_result.first.return_value = None
        mock_session.exec.side_effect = [
            members_result,
            preference_result,
            preference_result,
        ]

        result = await notify_org_members_by_role(
            mock_session,
            org_id,
            NotificationType.SERVICE_CHANGE,
            max_access_level=AccessLevel.OWNER,
            payload={"reason": "connection_established"},
        )

        assert len(result) == 2
        assert mock_session.add.call_count == 2
        assert mock_session.exec.call_count == 3

    async def test_skips_muted_members(self, mock_session: AsyncMock):
        """Test that members who have muted the notification type are skipped."""
        org_id = uuid.uuid4()
        user_ids = [uuid.uuid4()]

        members_result = MagicMock()
        members_result.all.return_value = user_ids
        preference_result = MagicMock()
        preference_result.first.return_value = True
        mock_session.exec.side_effect = [members_result, preference_result]

        result = await notify_org_members_by_role(
            mock_session,
            org_id,
            NotificationType.SERVICE_CHANGE,
            max_access_level=AccessLevel.ADMIN,
            payload={"reason": "connection_established"},
        )

        assert result == []
        mock_session.add.assert_not_called()


class TestGetUnreadCount:
    """Tests for the get_unread_count service function."""

    async def test_returns_count(self, mock_session: AsyncMock):
        """Test that get_unread_count returns the count from the query result."""
        count_result = MagicMock()
        count_result.one.return_value = 3
        mock_session.exec.return_value = count_result

        result = await get_unread_count(mock_session, uuid.uuid4())

        assert result == 3


class TestGetUnreadCountOrgFilter:
    """Tests for the org_id filter on get_unread_count."""

    async def test_scopes_to_org_when_given(self, mock_session: AsyncMock):
        """Test that passing org_id still executes a single count query."""
        count_result = MagicMock()
        count_result.one.return_value = 1
        mock_session.exec.return_value = count_result

        result = await get_unread_count(mock_session, uuid.uuid4(), org_id=uuid.uuid4())

        assert result == 1
        mock_session.exec.assert_called_once()


class TestGetNotifications:
    """Tests for the get_notifications service function."""

    async def test_executes_count_and_paginated_queries(self, mock_session: AsyncMock):
        """Test that get_notifications executes both queries and returns the results."""
        notification = Notification(
            user_id=uuid.uuid4(),
            type=NotificationType.EXECUTION_FINISHED,
            payload={"reason": "success"},
        )
        count_result = MagicMock()
        count_result.one.return_value = 1
        list_result = MagicMock()
        list_result.all.return_value = [notification]
        mock_session.exec.side_effect = [count_result, list_result]

        items, total = await get_notifications(
            mock_session, uuid.uuid4(), offset=0, limit=50
        )

        assert mock_session.exec.call_count == 2
        assert total == 1
        assert items == [notification]

    async def test_unread_only_adds_filter(self, mock_session: AsyncMock):
        """Test that unread_only=True still executes both queries with the extra filter applied."""
        count_result = MagicMock()
        count_result.one.return_value = 0
        list_result = MagicMock()
        list_result.all.return_value = []
        mock_session.exec.side_effect = [count_result, list_result]

        items, total = await get_notifications(
            mock_session, uuid.uuid4(), offset=0, limit=50, unread_only=True
        )

        assert mock_session.exec.call_count == 2
        assert total == 0
        assert items == []

    async def test_org_id_adds_filter(self, mock_session: AsyncMock):
        """Test that passing org_id still executes both queries with the extra filter applied."""
        count_result = MagicMock()
        count_result.one.return_value = 0
        list_result = MagicMock()
        list_result.all.return_value = []
        mock_session.exec.side_effect = [count_result, list_result]

        items, total = await get_notifications(
            mock_session, uuid.uuid4(), offset=0, limit=50, org_id=uuid.uuid4()
        )

        assert mock_session.exec.call_count == 2
        assert total == 0
        assert items == []


class TestGetNotificationById:
    """Tests for the get_notification_by_id service function."""

    async def test_calls_session_get(self, mock_session: AsyncMock):
        """Test that get_notification_by_id calls session.get with the correct parameters."""
        notification_id = uuid.uuid4()
        mock_session.get.return_value = None

        result = await get_notification_by_id(mock_session, notification_id)

        mock_session.get.assert_called_once_with(Notification, notification_id)
        assert result is None


class TestMarkAsRead:
    """Tests for the mark_as_read service function."""

    async def test_sets_read_at_when_unread(self, mock_session: AsyncMock):
        """Test that mark_as_read sets read_at and adds the notification to the session."""
        notification = Notification(
            user_id=uuid.uuid4(),
            type=NotificationType.EXECUTION_FINISHED,
            payload={"reason": "success"},
        )

        result = await mark_as_read(mock_session, notification)

        assert result.read_at is not None
        mock_session.add.assert_called_once_with(notification)

    async def test_noop_when_already_read(self, mock_session: AsyncMock):
        """Test that mark_as_read does not touch the session if the notification is already read."""
        notification = Notification(
            user_id=uuid.uuid4(),
            type=NotificationType.EXECUTION_FINISHED,
            payload={"reason": "success"},
            read_at=None,
        )
        await mark_as_read(mock_session, notification)
        mock_session.reset_mock()

        await mark_as_read(mock_session, notification)

        mock_session.add.assert_not_called()


class TestMarkAsUnread:
    """Tests for the mark_as_unread service function."""

    async def test_clears_read_at_when_read(self, mock_session: AsyncMock):
        """Test that mark_as_unread clears read_at and adds the notification to the session."""
        notification = Notification(
            user_id=uuid.uuid4(),
            type=NotificationType.EXECUTION_FINISHED,
            payload={"reason": "success"},
        )
        await mark_as_read(mock_session, notification)
        mock_session.reset_mock()

        result = await mark_as_unread(mock_session, notification)

        assert result.read_at is None
        mock_session.add.assert_called_once_with(notification)

    async def test_noop_when_already_unread(self, mock_session: AsyncMock):
        """Test that mark_as_unread does not touch the session if already unread."""
        notification = Notification(
            user_id=uuid.uuid4(),
            type=NotificationType.EXECUTION_FINISHED,
            payload={"reason": "success"},
            read_at=None,
        )

        await mark_as_unread(mock_session, notification)

        mock_session.add.assert_not_called()


class TestMarkAllAsRead:
    """Tests for the mark_all_as_read service function."""

    async def test_marks_every_unread_notification(self, mock_session: AsyncMock):
        """Test that mark_all_as_read sets read_at on every unread notification returned."""
        user_id = uuid.uuid4()
        unread = [
            Notification(
                user_id=user_id,
                type=NotificationType.EXECUTION_FINISHED,
                payload={"reason": "success"},
            ),
            Notification(
                user_id=user_id,
                type=NotificationType.EXECUTION_FINISHED,
                payload={"reason": "failed"},
            ),
        ]
        result_mock = MagicMock()
        result_mock.all.return_value = unread
        mock_session.exec.return_value = result_mock

        count = await mark_all_as_read(mock_session, user_id)

        assert count == 2
        assert all(n.read_at is not None for n in unread)
        assert mock_session.add.call_count == 2

    async def test_returns_zero_when_nothing_unread(self, mock_session: AsyncMock):
        """Test that mark_all_as_read returns 0 and touches nothing when there is no unread."""
        result_mock = MagicMock()
        result_mock.all.return_value = []
        mock_session.exec.return_value = result_mock

        count = await mark_all_as_read(mock_session, uuid.uuid4(), org_id=uuid.uuid4())

        assert count == 0
        mock_session.add.assert_not_called()


class TestGetPreferences:
    """Tests for the get_preferences service function."""

    async def test_defaults_unset_types_to_unmuted(self, mock_session: AsyncMock):
        """Test that mutable types without a stored preference default to unmuted (False)."""
        result_mock = MagicMock()
        result_mock.all.return_value = []
        mock_session.exec.return_value = result_mock

        preferences = await get_preferences(mock_session, uuid.uuid4())

        assert all(muted is False for muted in preferences.values())
        assert NotificationType.EXECUTION_FINISHED in preferences
        assert NotificationType.BILLING not in preferences

    async def test_returns_stored_preference(self, mock_session: AsyncMock):
        """Test that a stored preference overrides the default."""
        stored = NotificationPreference(
            user_id=uuid.uuid4(),
            notification_type=NotificationType.EXECUTION_FINISHED,
            muted=True,
        )
        result_mock = MagicMock()
        result_mock.all.return_value = [stored]
        mock_session.exec.return_value = result_mock

        preferences = await get_preferences(mock_session, uuid.uuid4())

        assert preferences[NotificationType.EXECUTION_FINISHED] is True


class TestSetPreference:
    """Tests for the set_preference service function."""

    async def test_creates_new_preference(self, mock_session: AsyncMock):
        """Test that set_preference creates a new NotificationPreference when none exists."""
        mock_session.exec.return_value.first.return_value = None
        user_id = uuid.uuid4()

        result = await set_preference(
            mock_session, user_id, NotificationType.EXECUTION_FINISHED, True
        )

        mock_session.add.assert_called_once()
        assert result.user_id == user_id
        assert result.muted is True

    async def test_updates_existing_preference(self, mock_session: AsyncMock):
        """Test that set_preference updates an existing NotificationPreference in place."""
        existing = NotificationPreference(
            user_id=uuid.uuid4(),
            notification_type=NotificationType.EXECUTION_FINISHED,
            muted=False,
        )
        mock_session.exec.return_value.first.return_value = existing

        result = await set_preference(
            mock_session, existing.user_id, NotificationType.EXECUTION_FINISHED, True
        )

        assert result is existing
        assert result.muted is True
        mock_session.add.assert_called_once_with(existing)
