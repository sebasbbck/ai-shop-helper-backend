import uuid

from sqlmodel import Field, SQLModel

from ai_shop_helper_backend.models.mixins import CreatedAtMixin, UUIDMixin


class GoogleAccount(UUIDMixin, CreatedAtMixin, SQLModel, table=True):
    """Maps a Google identity to a backend user, for login only.

    No OAuth tokens are stored here — per-project access to Google data
    (GA4, Search Console) is a separate concern, see connections/google.py.
    """

    user_id: uuid.UUID = Field(foreign_key="user.id", unique=True, index=True)
    google_id: str = Field(unique=True, index=True)
    google_email: str
