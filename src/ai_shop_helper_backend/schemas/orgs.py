from datetime import datetime
from uuid import UUID

from pydantic import Field
from sqlmodel import SQLModel

from ai_shop_helper_backend.schemas.projects import ProjectPublic


class OrgCreate(SQLModel):
    """Schema for creating a new organization."""

    name: str = Field(min_length=1, max_length=255)


class OrgUpdate(SQLModel):
    """Schema for updating an organization."""

    name: str | None = Field(default=None, min_length=1, max_length=255)


class OrgPublic(SQLModel):
    """Schema for returning organization data to the client."""

    id: UUID
    name: str
    subscription_credits: int
    purchased_credits: int
    created_at: datetime
    updated_at: datetime
    created_by: UUID
    updated_by: UUID


class OrgWithProjects(OrgPublic):
    """Schema for returning organization with nested projects."""

    projects: list[ProjectPublic] = []
