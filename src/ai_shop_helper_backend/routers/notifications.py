from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status

from ai_shop_helper_backend.core.constants import MUTABLE_NOTIFICATION_TYPES
from ai_shop_helper_backend.core.deps import CurrentUser, PaginationDep, SessionDep
from ai_shop_helper_backend.schemas.common import PaginatedResponse
from ai_shop_helper_backend.schemas.notifications import (
    MarkAllReadResponse,
    NotificationPreferencesResponse,
    NotificationPreferenceUpdate,
    NotificationPublic,
    UnreadCountResponse,
)
from ai_shop_helper_backend.services import notifications

router = APIRouter(prefix="/notifications", tags=["notifications"])


@router.get("/unread-count", response_model=UnreadCountResponse)
async def get_unread_count(
    current_user: CurrentUser,
    session: SessionDep,
    org_id: UUID | None = Query(default=None),
) -> UnreadCountResponse:
    """Get the current user's unread notification count. Meant to be polled periodically.

    Args:
        current_user (User): The current authenticated user.
        session (SessionDep): The database session.
        org_id (UUID | None): If given, only count notifications tied to this org.

    Returns:
        UnreadCountResponse: The unread notification count.
    """
    count = await notifications.get_unread_count(session, current_user.id, org_id)
    return UnreadCountResponse(unread_count=count)


@router.get("/", response_model=PaginatedResponse[NotificationPublic])
async def get_notifications(
    current_user: CurrentUser,
    pagination: PaginationDep,
    session: SessionDep,
    unread_only: bool = Query(default=False),
    org_id: UUID | None = Query(default=None),
) -> PaginatedResponse[NotificationPublic]:
    """Get a paginated list of the current user's notifications, newest first.

    Args:
        current_user (User): The current authenticated user.
        pagination (PaginationParams): The pagination parameters.
        session (SessionDep): The database session.
        unread_only (bool): Whether to only return unread notifications.
        org_id (UUID | None): If given, only return notifications tied to this org.

    Returns:
        PaginatedResponse[NotificationPublic]: The paginated list of notifications.
    """
    items, total = await notifications.get_notifications(
        session,
        current_user.id,
        pagination.offset,
        pagination.limit,
        unread_only,
        org_id,
    )
    return PaginatedResponse(
        items=[NotificationPublic.model_validate(n) for n in items],
        total=total,
        offset=pagination.offset,
        limit=pagination.limit,
    )


@router.patch("/read-all", response_model=MarkAllReadResponse)
async def mark_all_notifications_read(
    current_user: CurrentUser,
    session: SessionDep,
    org_id: UUID | None = Query(default=None),
) -> MarkAllReadResponse:
    """Mark all of the current user's unread notifications as read.

    Args:
        current_user (User): The current authenticated user.
        session (SessionDep): The database session.
        org_id (UUID | None): If given, only mark notifications tied to this org as read.

    Returns:
        MarkAllReadResponse: The number of notifications marked as read.
    """
    marked_count = await notifications.mark_all_as_read(
        session, current_user.id, org_id
    )
    return MarkAllReadResponse(marked_count=marked_count)


@router.patch("/{notification_id}/read", response_model=NotificationPublic)
async def mark_notification_read(
    notification_id: UUID,
    current_user: CurrentUser,
    session: SessionDep,
) -> NotificationPublic:
    """Mark one of the current user's notifications as read.

    Args:
        notification_id (UUID): The notification ID.
        current_user (User): The current authenticated user.
        session (SessionDep): The database session.

    Returns:
        NotificationPublic: The updated notification.

    Raises:
        HTTPException: 404 if the notification does not exist or belongs to another user.
    """
    notification = await notifications.get_notification_by_id(session, notification_id)
    if not notification or notification.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Notification not found",
        )
    updated = await notifications.mark_as_read(session, notification)
    return NotificationPublic.model_validate(updated)


@router.patch("/{notification_id}/unread", response_model=NotificationPublic)
async def mark_notification_unread(
    notification_id: UUID,
    current_user: CurrentUser,
    session: SessionDep,
) -> NotificationPublic:
    """Mark one of the current user's notifications as unread.

    Args:
        notification_id (UUID): The notification ID.
        current_user (User): The current authenticated user.
        session (SessionDep): The database session.

    Returns:
        NotificationPublic: The updated notification.

    Raises:
        HTTPException: 404 if the notification does not exist or belongs to another user.
    """
    notification = await notifications.get_notification_by_id(session, notification_id)
    if not notification or notification.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Notification not found",
        )
    updated = await notifications.mark_as_unread(session, notification)
    return NotificationPublic.model_validate(updated)


@router.get("/preferences", response_model=NotificationPreferencesResponse)
async def get_notification_preferences(
    current_user: CurrentUser, session: SessionDep
) -> NotificationPreferencesResponse:
    """Get the current user's mute preferences for every mutable notification type.

    Args:
        current_user (User): The current authenticated user.
        session (SessionDep): The database session.

    Returns:
        NotificationPreferencesResponse: The mapping of notification type to muted state.
    """
    preferences = await notifications.get_preferences(session, current_user.id)
    return NotificationPreferencesResponse(preferences=preferences)


@router.patch("/preferences", response_model=NotificationPreferencesResponse)
async def update_notification_preference(
    preference_in: NotificationPreferenceUpdate,
    current_user: CurrentUser,
    session: SessionDep,
) -> NotificationPreferencesResponse:
    """Mute or unmute a notification type for the current user.

    Args:
        preference_in (NotificationPreferenceUpdate): The notification type and desired muted state.
        current_user (User): The current authenticated user.
        session (SessionDep): The database session.

    Returns:
        NotificationPreferencesResponse: The updated mapping of notification type to muted state.

    Raises:
        HTTPException: 400 if the notification type cannot be muted.
    """
    if preference_in.notification_type not in MUTABLE_NOTIFICATION_TYPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This notification type cannot be muted",
        )
    await notifications.set_preference(
        session,
        current_user.id,
        preference_in.notification_type,
        preference_in.muted,
    )
    preferences = await notifications.get_preferences(session, current_user.id)
    return NotificationPreferencesResponse(preferences=preferences)
