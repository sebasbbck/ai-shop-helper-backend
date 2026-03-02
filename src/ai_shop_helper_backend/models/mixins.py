import uuid
from datetime import datetime

from sqlmodel import Field, SQLModel

from ai_shop_helper_backend.core.utils import get_datetime_utc


class CreatedAtMixin(SQLModel):
    """Mixin that adds a created_at field to a SQLModel model, which is automatically set
    to the current UTC datetime when the model is created.
    """

    created_at: datetime = Field(default_factory=get_datetime_utc)


class UpdatedAtMixin(SQLModel):
    """Mixin that adds an updated_at field to a SQLModel model, which is automatically
    updated to the current UTC datetime whenever the model is updated.
    """

    updated_at: datetime = Field(
        default_factory=get_datetime_utc,
        sa_column_kwargs={"onupdate": get_datetime_utc},
    )


class TimestampMixin(CreatedAtMixin, UpdatedAtMixin):
    """Mixin that adds created_at and updated_at fields to a SQLModel model."""

    pass


class UUIDMixin(SQLModel):
    """Mixin that adds a UUID primary key field to a SQLModel model."""

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
