import base64

from ai_shop_helper_backend.connections.base import decode_secrets
from ai_shop_helper_backend.models.connections import Connection


class WordpressProvider:
    async def get_injected_inputs(self, connection: Connection) -> dict[str, str]:
        secrets = decode_secrets(connection)
        raw = f"{secrets['username']}:{secrets['app_password']}"
        auth_token = base64.b64encode(raw.encode()).decode()
        return {"url": secrets["site_url"], "auth_token": auth_token}
