from typing import Generic, TypeVar

from pydantic import BaseModel

T = TypeVar("T")


class PaginatedResponse(BaseModel, Generic[T]):
    """Schema for paginated responses."""

    items: list[T]
    total: int
    offset: int
    limit: int
