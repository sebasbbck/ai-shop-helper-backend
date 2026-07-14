from datetime import datetime
from uuid import UUID

from sqlmodel import Field, SQLModel

from ai_shop_helper_backend.core.utils import get_datetime_utc
from ai_shop_helper_backend.models.mixins import CreatedAtMixin, UUIDMixin


class AuthEmailToken(CreatedAtMixin, UUIDMixin, SQLModel, table=True):
    """Single-use token for email verification and password reset."""

    __tablename__ = "authemailtoken"

    user_id: UUID = Field(foreign_key="user.id", index=True)
    token: str = Field(unique=True, index=True, max_length=255)
    purpose: str = Field(max_length=32)
    expires_at: datetime
    used_at: datetime | None = None


class EmailOutbox(CreatedAtMixin, UUIDMixin, SQLModel, table=True):
    """Transactional email outbox for reliable, idempotent delivery via the poller."""

    __tablename__ = "emailoutbox"

    to_email: str = Field(max_length=255, index=True)
    first_name: str | None = Field(default=None, max_length=255)
    email_type: str = Field(max_length=64)
    locale: str = Field(max_length=16)
    data_json: str = Field(max_length=8192)
    external_id: str = Field(unique=True, index=True, max_length=255)
    status: str = Field(max_length=16, default="pending", index=True)
    attempts: int = 0
    next_attempt_at: datetime = Field(default_factory=get_datetime_utc, index=True)
    last_error: str | None = Field(default=None, max_length=2048)
    sent_at: datetime | None = None
