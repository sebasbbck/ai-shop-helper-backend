from datetime import datetime
from uuid import UUID

import sqlalchemy as sa
from sqlmodel import Column, Field, SQLModel

from ai_shop_helper_backend.models.mixins import TimestampMixin, UUIDMixin


class GoogleCredential(UUIDMixin, TimestampMixin, SQLModel, table=True):
    """Stores Google OAuth2 credentials linked to a backend user."""

    user_id: UUID = Field(foreign_key="user.id", unique=True, index=True)
    google_id: str = Field(unique=True, index=True)
    google_email: str
    access_token: str
    refresh_token: str
    token_expires_at: datetime = Field(
        sa_column=Column(sa.DateTime(timezone=True), nullable=False)
    )
    scopes: str
