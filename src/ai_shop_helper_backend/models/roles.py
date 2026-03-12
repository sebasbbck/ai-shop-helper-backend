from sqlmodel import Field, SQLModel

from ai_shop_helper_backend.models.mixins import AuditMixin, UUIDMixin


class Role(UUIDMixin, AuditMixin, SQLModel, table=True):
    """Role model representing user roles in organizations."""

    name: str = Field(unique=True, max_length=255)
    description: str | None = Field(default=None)
    access_level: int
