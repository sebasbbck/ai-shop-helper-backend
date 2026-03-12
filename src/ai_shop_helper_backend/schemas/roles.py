from datetime import datetime
from uuid import UUID

from pydantic import Field
from sqlmodel import SQLModel


class RoleCreate(SQLModel):
    """Schema for creating a new role."""

    name: str = Field(min_length=1, max_length=255)
    description: str | None = None
    access_level: int = Field(ge=0, le=100)  # 0=highest, 100=lowest


class RoleUpdate(SQLModel):
    """Schema for updating a role."""

    name: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = None
    access_level: int | None = Field(default=None, ge=0, le=100)


class RolePublic(SQLModel):
    """Schema for returning role data to the client."""

    id: UUID
    name: str
    description: str | None
    access_level: int
    created_at: datetime
    updated_at: datetime
    created_by: UUID
    updated_by: UUID
