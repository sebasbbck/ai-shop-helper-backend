from datetime import datetime
from uuid import UUID

from sqlmodel import Field, SQLModel

from ai_shop_helper_backend.models.mixins import UUIDMixin


class WordpressToken(UUIDMixin, SQLModel, table=True):
    """Short-lived handshake token linking a pending WordPress OAuth to a project."""

    __tablename__ = "wordpresstoken"

    token: str = Field(max_length=128, unique=True, index=True)
    project_id: UUID = Field(foreign_key="project.id", index=True)
    expires_at: datetime
