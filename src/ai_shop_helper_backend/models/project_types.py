from sqlmodel import Field, SQLModel

from ai_shop_helper_backend.models.mixins import AuditMixin, UUIDMixin


class ProjectType(UUIDMixin, AuditMixin, SQLModel, table=True):
    __tablename__ = "projecttype"

    name: str = Field(unique=True, max_length=255)
