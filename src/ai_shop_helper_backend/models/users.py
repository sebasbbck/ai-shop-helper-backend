from pydantic import EmailStr
from sqlmodel import Field, SQLModel

from ai_shop_helper_backend.models.mixins import TimestampMixin, UUIDMixin


class User(TimestampMixin, UUIDMixin, SQLModel, table=True):
    """User model representing a user in the system."""

    email: EmailStr = Field(unique=True, index=True, max_length=255)
    name: str = Field(max_length=255)
    is_superuser: bool = False
    is_active: bool = True
    hashed_password: str
