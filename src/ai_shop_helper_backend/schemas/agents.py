from datetime import datetime
from uuid import UUID

from pydantic import Field
from sqlmodel import SQLModel


class AgentCreate(SQLModel):
    """Schema for creating a new agent."""

    name: str = Field(min_length=1, max_length=255)
    description: str | None = None


class AgentUpdate(SQLModel):
    """Schema for updating an agent."""

    name: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = None


class AgentPublic(SQLModel):
    """Schema for returning agent data to the client."""

    id: UUID
    name: str
    description: str | None
    created_at: datetime
    updated_at: datetime
    created_by: UUID
    updated_by: UUID
