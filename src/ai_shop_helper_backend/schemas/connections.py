from sqlmodel import SQLModel

from ai_shop_helper_backend.models.connections import ConnectionType


class ConnectionAvailability(SQLModel):
    """Whether a connection type relevant to a project is already connected."""

    connection_type: ConnectionType
    connected: bool


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


class PrestashopConnectBody(SQLModel):
    """Request body for connecting a PrestaShop store via its Webservice API key."""

    shop_url: str
    ws_key: str


class PrestashopStatusResponse(SQLModel):
    """Connection status for a project — never includes the webservice key."""

    connected: bool
    shop_url: str | None = None
