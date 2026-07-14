from sqlmodel import Field, SQLModel

from ai_shop_helper_backend.models.mixins import AuditMixin, UUIDMixin


class Org(UUIDMixin, AuditMixin, SQLModel, table=True):
    """Organization model representing an organization in the system."""

    name: str = Field(unique=True, max_length=255)
    subscription_credits: int = Field(default=0, ge=0)
    purchased_credits: int = Field(default=0, ge=0)
