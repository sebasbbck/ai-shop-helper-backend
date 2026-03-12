from sqlmodel import Field, SQLModel

from ai_shop_helper_backend.models.mixins import AuditMixin, UUIDMixin


class ProjectType(UUIDMixin, AuditMixin, SQLModel, table=True):
    """Project type model representing different types of projects."""

    name: str = Field(unique=True, max_length=255)
