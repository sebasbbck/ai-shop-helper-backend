from datetime import datetime
from uuid import UUID

from pydantic import EmailStr
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


class OrgMemberUser(SQLModel):
    """Least-exposure view of a member's user identity for org listings."""

    id: UUID
    name: str
    email: EmailStr


class OrgMemberRole(SQLModel):
    """Compact view of a member's org role."""

    id: UUID
    name: str
    access_level: int


class OrgMemberPublic(SQLModel):
    """Enriched member row for display: membership with nested user and role."""

    id: UUID
    org_id: UUID
    user: OrgMemberUser
    role: OrgMemberRole
    created_at: datetime
    updated_at: datetime
