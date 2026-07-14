import json
from typing import Protocol

from ai_shop_helper_backend.core.crypto import decrypt
from ai_shop_helper_backend.models.connections import Connection


def decode_secrets(connection: Connection) -> dict:
    return json.loads(decrypt(connection.secrets_encrypted))


class ConnectionProvider(Protocol):
    async def get_injected_inputs(self, connection: Connection) -> dict[str, str]: ...
