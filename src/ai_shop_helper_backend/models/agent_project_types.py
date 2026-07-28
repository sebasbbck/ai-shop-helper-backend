from uuid import UUID

from sqlalchemy import UniqueConstraint
from sqlmodel import Field, SQLModel

from ai_shop_helper_backend.models.mixins import AuditMixin, UUIDMixin


class AgentProjectType(UUIDMixin, AuditMixin, SQLModel, table=True):
    """AgentProjectType model representing the relationship between agents and project types."""

    __table_args__ = (UniqueConstraint("agent_id", "project_type_id"),)

    agent_id: UUID = Field(foreign_key="agent.id")
    project_type_id: UUID = Field(foreign_key="projecttype.id", index=True)
