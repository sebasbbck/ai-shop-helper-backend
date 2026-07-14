from sqlmodel import SQLModel


class WordpressStartBody(SQLModel):
    """Request body for initiating a WordPress connection."""

    site_url: str


class WordpressStartResponse(SQLModel):
    """Response containing the redirect URL to send the browser to."""

    redirect_url: str


class WordpressStatusResponse(SQLModel):
    """Connection status for a project — never includes the password."""

    connected: bool
    site_url: str | None = None
    username: str | None = None
