from uuid import UUID

from sqlalchemy import UniqueConstraint
from sqlmodel import Field, SQLModel

from ai_shop_helper_backend.models.mixins import AuditMixin, UUIDMixin


class Project(UUIDMixin, AuditMixin, SQLModel, table=True):
    """Project model representing a project part of an organization."""

    __table_args__ = (UniqueConstraint("org_id", "name"),)

    org_id: UUID = Field(foreign_key="org.id")
    name: str = Field(max_length=255)
    project_type_id: UUID = Field(foreign_key="projecttype.id", index=True)
    # url: str = Field(max_length=1024)
    # is_connected: bool = Field(default=False)
    # access_token: str | None = Field(default=None)
