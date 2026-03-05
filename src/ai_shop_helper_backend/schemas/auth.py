from sqlmodel import SQLModel


class Token(SQLModel):
    """Schema for the access token response."""

    access_token: str
    token_type: str = "bearer"
