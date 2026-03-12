from datetime import datetime
from uuid import UUID

from pydantic import Field
from sqlmodel import SQLModel


class ProjectTypeCreate(SQLModel):
    """Schema for creating a new project type."""

    name: str = Field(min_length=1, max_length=255)


class ProjectTypeUpdate(SQLModel):
    """Schema for updating a project type."""

    name: str | None = Field(default=None, min_length=1, max_length=255)


class ProjectTypePublic(SQLModel):
    """Schema for returning project type data to the client."""

    id: UUID
    name: str
    created_at: datetime
    updated_at: datetime
    created_by: UUID
    updated_by: UUID
