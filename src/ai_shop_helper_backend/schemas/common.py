from typing import Generic, TypeVar

from sqlmodel import SQLModel

T = TypeVar("T")


class PaginatedResponse(SQLModel, Generic[T]):
    """Schema for paginated responses."""

    items: list[T]
    total: int
    offset: int
    limit: int
