import base64

from sqlmodel.ext.asyncio.session import AsyncSession

from ai_shop_helper_backend.connections.base import decode_secrets
from ai_shop_helper_backend.models.connections import Connection


class WordpressProvider:
    async def get_credentials(
        self, session: AsyncSession, connection: Connection
    ) -> dict:
        return decode_secrets(connection)

    def to_injected_inputs(self, credentials: dict) -> dict[str, str]:
        raw = f"{credentials['username']}:{credentials['app_password']}"
        auth_token = base64.b64encode(raw.encode()).decode()
        return {"url": credentials["site_url"], "auth_token": auth_token}
