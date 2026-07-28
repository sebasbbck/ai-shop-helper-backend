from datetime import datetime
from uuid import UUID

from sqlmodel import SQLModel


class AgentProjectTypeCreate(SQLModel):
    """Schema for creating a new agent-project type relationship."""

    agent_id: UUID
    project_type_id: UUID


class AgentProjectTypePublic(SQLModel):
    """Schema for returning agent-project type relationship data to the client."""

    id: UUID
    agent_id: UUID
    project_type_id: UUID
    created_at: datetime
    updated_at: datetime
    created_by: UUID
    updated_by: UUID
