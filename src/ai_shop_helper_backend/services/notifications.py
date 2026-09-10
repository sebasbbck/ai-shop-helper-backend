from collections.abc import Sequence
from uuid import UUID

from sqlmodel import col, func, select
from sqlmodel.ext.asyncio.session import AsyncSession

from ai_shop_helper_backend.core.constants import MUTABLE_NOTIFICATION_TYPES
from ai_shop_helper_backend.core.utils import get_datetime_utc
from ai_shop_helper_backend.models.notifications import (
    Notification,
    NotificationPreference,
)
from ai_shop_helper_backend.models.org_users import OrgUser
from ai_shop_helper_backend.models.roles import Role


async def _is_muted(
    session: AsyncSession, user_id: UUID, notification_type: str
) -> bool:
    if notification_type not in MUTABLE_NOTIFICATION_TYPES:
        return False
    result = await session.exec(
        select(NotificationPreference.muted).where(
            NotificationPreference.user_id == user_id,
            NotificationPreference.notification_type == notification_type,
        )
    )
    muted = result.first()
    return bool(muted)


async def create_notification(
    session: AsyncSession,
    user_id: UUID,
    notification_type: str,
    org_id: UUID | None = None,
    payload: dict | None = None,
) -> Notification | None:
    """Create a notification for a user, unless they have muted this type.

    The frontend owns all copy: it renders the notification text from `notification_type`
    plus `payload` (see `Notifications.messages.<type>.<payload.reason>` in the frontend's
    i18n catalogs), so no title/body text is generated here.

    Args:
        session (AsyncSession): The database session.
        user_id (UUID): The recipient user ID.
        notification_type (str): The notification type (see NotificationType constants).
        org_id (UUID | None): The related organization ID, if any.
        payload (dict | None): Structured data the frontend uses to render the localized
            text — by convention includes a "reason" key selecting the message variant.

    Returns:
        Notification | None: The created notification, or None if the user has muted this type.
    """
    if await _is_muted(session, user_id, notification_type):
        return None

    notification = Notification(
        user_id=user_id,
        org_id=org_id,
        type=notification_type,
        payload=payload,
    )
    session.add(notification)
    return notification


async def notify_org_members_by_role(
    session: AsyncSession,
    org_id: UUID,
    notification_type: str,
    max_access_level: int,
    payload: dict | None = None,
) -> list[Notification]:
    """Create a notification for every org member whose role access_level is within the given bound.

    Role-aware dispatch primitive: e.g. pass AccessLevel.OWNER to target only org owners
    (billing notifications), or AccessLevel.ADMIN to target admins and owners.

    Args:
        session (AsyncSession): The database session.
        org_id (UUID): The organization ID.
        notification_type (str): The notification type (see NotificationType constants).
        max_access_level (int): The maximum access_level (inclusive) a member's role may have to qualify.
        payload (dict | None): Structured data the frontend uses to render the localized text.

    Returns:
        list[Notification]: The notifications created (muted recipients are skipped).
    """
    result = await session.exec(
        select(OrgUser.user_id)
        .join(Role, col(OrgUser.role_id) == col(Role.id))
        .where(OrgUser.org_id == org_id, Role.access_level <= max_access_level)
    )
    user_ids = result.all()

    notifications = []
    for user_id in user_ids:
        notification = await create_notification(
            session,
            user_id,
            notification_type,
            org_id=org_id,
            payload=payload,
        )
        if notification:
            notifications.append(notification)
    return notifications


async def get_unread_count(
    session: AsyncSession, user_id: UUID, org_id: UUID | None = None
) -> int:
    """Count unread notifications for a user.

    Args:
        session (AsyncSession): The database session.
        user_id (UUID): The user ID.
        org_id (UUID | None): If given, only count notifications tied to this org.

    Returns:
        int: The number of unread notifications.
    """
    filters = [Notification.user_id == user_id, col(Notification.read_at).is_(None)]
    if org_id is not None:
        filters.append(Notification.org_id == org_id)

    result = await session.exec(
        select(func.count()).select_from(Notification).where(*filters)
    )
    return result.one()


async def get_notifications(
    session: AsyncSession,
    user_id: UUID,
    offset: int,
    limit: int,
    unread_only: bool = False,
    org_id: UUID | None = None,
) -> tuple[Sequence[Notification], int]:
    """Get a paginated list of a user's notifications, newest first.

    Args:
        session (AsyncSession): The database session.
        user_id (UUID): The user ID.
        offset (int): The number of notifications to skip.
        limit (int): The maximum number of notifications to return.
        unread_only (bool): Whether to only return unread notifications.
        org_id (UUID | None): If given, only return notifications tied to this org.

    Returns:
        tuple[Sequence[Notification], int]: A tuple containing the list of notifications
            and the total count.
    """
    filters = [Notification.user_id == user_id]
    if unread_only:
        filters.append(col(Notification.read_at).is_(None))
    if org_id is not None:
        filters.append(Notification.org_id == org_id)

    total_result = await session.exec(
        select(func.count()).select_from(Notification).where(*filters)
    )
    notifications_result = await session.exec(
        select(Notification)
        .where(*filters)
        .order_by(col(Notification.created_at).desc())
        .offset(offset)
        .limit(limit)
    )
    return notifications_result.all(), total_result.one()


async def get_notification_by_id(
    session: AsyncSession, notification_id: UUID
) -> Notification | None:
    """Get a notification by ID.

    Args:
        session (AsyncSession): The database session.
        notification_id (UUID): The notification ID.

    Returns:
        Notification | None: The notification if found, None otherwise.
    """
    return await session.get(Notification, notification_id)


async def mark_as_read(
    session: AsyncSession, notification: Notification
) -> Notification:
    """Mark a notification as read, if it isn't already.

    Args:
        session (AsyncSession): The database session.
        notification (Notification): The notification to mark as read.

    Returns:
        Notification: The updated notification.
    """
    if notification.read_at is None:
        notification.read_at = get_datetime_utc()
        session.add(notification)
    return notification


async def mark_as_unread(
    session: AsyncSession, notification: Notification
) -> Notification:
    """Mark a notification as unread, if it isn't already.

    Symmetric to mark_as_read — lets a user move a notification back to the
    unread state from the dedicated notifications view.

    Args:
        session (AsyncSession): The database session.
        notification (Notification): The notification to mark as unread.

    Returns:
        Notification: The updated notification.
    """
    if notification.read_at is not None:
        notification.read_at = None
        session.add(notification)
    return notification


async def mark_all_as_read(
    session: AsyncSession, user_id: UUID, org_id: UUID | None = None
) -> int:
    """Mark all of a user's unread notifications as read.

    Args:
        session (AsyncSession): The database session.
        user_id (UUID): The user ID.
        org_id (UUID | None): If given, only mark notifications tied to this org as read.

    Returns:
        int: The number of notifications marked as read.
    """
    filters = [Notification.user_id == user_id, col(Notification.read_at).is_(None)]
    if org_id is not None:
        filters.append(Notification.org_id == org_id)

    result = await session.exec(select(Notification).where(*filters))
    unread = result.all()
    now = get_datetime_utc()
    for notification in unread:
        notification.read_at = now
        session.add(notification)
    return len(unread)


async def get_preferences(session: AsyncSession, user_id: UUID) -> dict[str, bool]:
    """Get a user's notification preferences for every mutable notification type.

    Types the user has never configured default to unmuted (False).

    Args:
        session (AsyncSession): The database session.
        user_id (UUID): The user ID.

    Returns:
        dict[str, bool]: A mapping of notification type to muted state.
    """
    result = await session.exec(
        select(NotificationPreference).where(NotificationPreference.user_id == user_id)
    )
    stored = {p.notification_type: p.muted for p in result.all()}
    return {t: stored.get(t, False) for t in MUTABLE_NOTIFICATION_TYPES}


async def set_preference(
    session: AsyncSession, user_id: UUID, notification_type: str, muted: bool
) -> NotificationPreference:
    """Create or update a user's mute preference for a notification type.

    Args:
        session (AsyncSession): The database session.
        user_id (UUID): The user ID.
        notification_type (str): The notification type to configure.
        muted (bool): Whether to mute this notification type.

    Returns:
        NotificationPreference: The created or updated preference.
    """
    result = await session.exec(
        select(NotificationPreference).where(
            NotificationPreference.user_id == user_id,
            NotificationPreference.notification_type == notification_type,
        )
    )
    preference = result.first()
    if preference:
        preference.muted = muted
        session.add(preference)
        return preference

    preference = NotificationPreference(
        user_id=user_id, notification_type=notification_type, muted=muted
    )
    session.add(preference)
    return preference
