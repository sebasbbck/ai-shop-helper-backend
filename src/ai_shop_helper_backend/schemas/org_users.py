from datetime import datetime
from uuid import UUID

from sqlmodel import SQLModel


class OrgUserCreate(SQLModel):
    """Schema for adding a member to an organization."""

    user_id: UUID
    org_id: UUID
    role_id: UUID


class OrgUserUpdate(SQLModel):
    """Schema for updating a member's role."""

    role_id: UUID


class OrgUserPublic(SQLModel):
    """Schema for returning org membership data to the client."""

    id: UUID
    user_id: UUID
    org_id: UUID
    role_id: UUID
    created_at: datetime
    updated_at: datetime
    created_by: UUID
    updated_by: UUID
