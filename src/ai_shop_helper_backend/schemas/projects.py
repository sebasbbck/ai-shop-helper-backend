from datetime import datetime
from uuid import UUID

from pydantic import Field
from sqlmodel import SQLModel


class ProjectCreate(SQLModel):
    """Schema for creating a new project."""

    org_id: UUID
    name: str = Field(min_length=1, max_length=255)
    project_type_id: UUID


class ProjectUpdate(SQLModel):
    """Schema for updating a project."""

    name: str | None = Field(default=None, min_length=1, max_length=255)
    project_type_id: UUID | None = None


class ProjectPublic(SQLModel):
    """Schema for returning project data to the client."""

    id: UUID
    org_id: UUID
    name: str
    project_type_id: UUID
    created_at: datetime
    updated_at: datetime
    created_by: UUID
    updated_by: UUID
