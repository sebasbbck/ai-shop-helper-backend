from sqlalchemy import Column
from sqlalchemy import Enum as SAEnum
from sqlmodel import Field, SQLModel

from ai_shop_helper_backend.models.connections import ConnectionType
from ai_shop_helper_backend.models.mixins import AuditMixin, UUIDMixin


class ProjectType(UUIDMixin, AuditMixin, SQLModel, table=True):
    __tablename__ = "projecttype"

    name: str = Field(unique=True, max_length=255)
    connection_type: ConnectionType | None = Field(
        default=None,
        sa_column=Column(SAEnum(ConnectionType, name="connectiontype"), nullable=True),
    )
