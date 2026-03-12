from datetime import datetime
from uuid import UUID

from pydantic import Field
from sqlmodel import SQLModel


class OrgCreate(SQLModel):
    """Schema for creating a new organization."""

    name: str = Field(min_length=1, max_length=255)


class OrgUpdate(SQLModel):
    """Schema for updating an organization."""

    name: str | None = Field(default=None, min_length=1, max_length=255)
    credits: int | None = Field(default=None, ge=0)


class OrgPublic(SQLModel):
    """Schema for returning organization data to the client."""

    id: UUID
    name: str
    credits: int
    created_at: datetime
    updated_at: datetime
    created_by: UUID
    updated_by: UUID
