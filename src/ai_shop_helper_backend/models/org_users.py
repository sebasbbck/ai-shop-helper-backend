from uuid import UUID

from sqlalchemy import UniqueConstraint
from sqlmodel import Field, SQLModel

from ai_shop_helper_backend.models.mixins import AuditMixin, UUIDMixin


class OrgUser(UUIDMixin, AuditMixin, SQLModel, table=True):
    """OrgUser model representing the relationship between users and organizations."""

    __table_args__ = (UniqueConstraint("user_id", "org_id"),)

    user_id: UUID = Field(foreign_key="user.id")
    org_id: UUID = Field(foreign_key="org.id", index=True)
    role_id: UUID = Field(foreign_key="role.id", index=True)
