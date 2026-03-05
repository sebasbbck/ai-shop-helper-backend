from datetime import datetime
from uuid import UUID

from sqlmodel import Field, SQLModel

from ai_shop_helper_backend.models.mixins import CreatedAtMixin, UUIDMixin


class RefreshToken(CreatedAtMixin, UUIDMixin, SQLModel, table=True):
    """Model representing a refresh token for user authentication."""

    user_id: UUID = Field(foreign_key="user.id", index=True)
    token: str = Field(index=True, unique=True)
    expires_at: datetime
