import uuid
from datetime import datetime

import sqlalchemy as sa
from sqlmodel import Column, Field, SQLModel

from ai_shop_helper_backend.models.mixins import CreatedAtMixin, UUIDMixin


class Notification(UUIDMixin, CreatedAtMixin, SQLModel, table=True):
    """Notification model representing an in-app notification for a user."""

    __table_args__ = (sa.Index("ix_notification_user_read", "user_id", "read_at"),)

    user_id: uuid.UUID = Field(foreign_key="user.id")
    org_id: uuid.UUID | None = Field(default=None, foreign_key="org.id")
    type: str = Field(max_length=50, index=True)
    payload: dict | None = Field(default=None, sa_column=Column(sa.JSON))
    read_at: datetime | None = Field(default=None)


class NotificationPreference(UUIDMixin, SQLModel, table=True):
    """Stores which notification types a user has muted."""

    __table_args__ = (sa.UniqueConstraint("user_id", "notification_type"),)

    user_id: uuid.UUID = Field(foreign_key="user.id")
    notification_type: str = Field(max_length=50)
    muted: bool = Field(default=False)
