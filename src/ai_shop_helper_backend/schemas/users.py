from datetime import datetime
from uuid import UUID

from pydantic import EmailStr, Field, SecretStr
from sqlmodel import SQLModel


class UserCreate(SQLModel):
    """Schema for creating a new user."""

    email: EmailStr
    name: str
    password: SecretStr = Field(min_length=8, max_length=128)


class UserUpdate(SQLModel):
    """Schema for updating the current user's own profile."""

    email: EmailStr | None = None
    name: str | None = None
    password: SecretStr | None = Field(default=None, min_length=8, max_length=128)


class UserAdminUpdate(SQLModel):
    """Schema for superuser updating any user."""

    email: EmailStr | None = None
    name: str | None = None
    password: SecretStr | None = Field(default=None, min_length=8, max_length=128)
    is_active: bool | None = None
    is_superuser: bool | None = None


class UserPublic(SQLModel):
    """Schema for returning user data to the client."""

    id: UUID
    email: EmailStr
    name: str
    is_active: bool
    is_superuser: bool
    created_at: datetime
    updated_at: datetime
