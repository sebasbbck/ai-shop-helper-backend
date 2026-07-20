import enum
import uuid

from sqlalchemy import Column, UniqueConstraint
from sqlalchemy import Enum as SAEnum
from sqlmodel import Field, SQLModel

from ai_shop_helper_backend.models.mixins import TimestampMixin, UUIDMixin


class ConnectionType(enum.StrEnum):
    wordpress = "wordpress"


class Connection(UUIDMixin, TimestampMixin, SQLModel, table=True):
    __tablename__ = "connection"
    __table_args__ = (
        UniqueConstraint(
            "project_id", "connection_type", name="uq_connection_project_type"
        ),
    )

    project_id: uuid.UUID = Field(foreign_key="project.id", index=True)
    connection_type: ConnectionType = Field(
        sa_column=Column(SAEnum(ConnectionType, name="connectiontype"), nullable=False)
    )
    secrets_encrypted: str = Field(max_length=8192)
    created_by: uuid.UUID | None = Field(
        default=None, foreign_key="user.id", nullable=True
    )
