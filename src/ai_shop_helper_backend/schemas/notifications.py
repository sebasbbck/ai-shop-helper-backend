from datetime import datetime
from uuid import UUID

from sqlmodel import SQLModel


class NotificationPublic(SQLModel):
    """Schema for a notification returned to the client."""

    id: UUID
    type: str
    payload: dict | None
    read_at: datetime | None
    created_at: datetime


class UnreadCountResponse(SQLModel):
    """Schema for the unread notification count, polled periodically by the client."""

    unread_count: int


class MarkAllReadResponse(SQLModel):
    """Schema for the result of bulk-marking notifications as read."""

    marked_count: int


class NotificationPreferenceUpdate(SQLModel):
    """Schema for muting/unmuting a notification type."""

    notification_type: str
    muted: bool


class NotificationPreferencesResponse(SQLModel):
    """Schema mapping each mutable notification type to its muted state."""

    preferences: dict[str, bool]
