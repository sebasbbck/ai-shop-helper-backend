import enum
import uuid

from sqlalchemy import Column
from sqlalchemy import Enum as SAEnum
from sqlalchemy import UniqueConstraint
from sqlmodel import Field, SQLModel

from ai_shop_helper_backend.models.mixins import TimestampMixin, UUIDMixin


class ConnectionType(str, enum.Enum):
    wordpress = "wordpress"


class Connection(UUIDMixin, TimestampMixin, SQLModel, table=True):
    __tablename__ = "connection"
    __table_args__ = (UniqueConstraint("project_id"),)

    project_id: uuid.UUID = Field(foreign_key="project.id", index=True)
    connection_type: ConnectionType = Field(
        sa_column=Column(SAEnum(ConnectionType, name="connectiontype"), nullable=False)
    )
    secrets_encrypted: str = Field(max_length=8192)
    created_by: uuid.UUID | None = Field(default=None, foreign_key="user.id", nullable=True)
