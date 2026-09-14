import base64

from sqlmodel.ext.asyncio.session import AsyncSession

from ai_shop_helper_backend.connections.base import decode_secrets
from ai_shop_helper_backend.models.connections import Connection


class PrestashopProvider:
    async def get_credentials(
        self, session: AsyncSession, connection: Connection
    ) -> dict:
        return decode_secrets(connection)

    def to_injected_inputs(self, credentials: dict) -> dict[str, str]:
        raw = f"{credentials['ws_key']}:"
        auth_token = base64.b64encode(raw.encode()).decode()
        return {"url": credentials["api_url"], "auth_token": auth_token}
