from sqlmodel import Field, SQLModel

from ai_shop_helper_backend.models.mixins import AuditMixin, UUIDMixin


class Agent(UUIDMixin, AuditMixin, SQLModel, table=True):
    """Agent model representing ai agents that interact with projects."""

    name: str = Field(unique=True, max_length=255)
    description: str | None = Field(default=None)
