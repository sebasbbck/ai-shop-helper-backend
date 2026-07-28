import json
from typing import Protocol

from sqlmodel.ext.asyncio.session import AsyncSession

from ai_shop_helper_backend.core.crypto import decrypt
from ai_shop_helper_backend.models.connections import Connection


def decode_secrets(connection: Connection) -> dict:
    return json.loads(decrypt(connection.secrets_encrypted))


class ConnectionProvider(Protocol):
    async def get_credentials(
        self, session: AsyncSession, connection: Connection
    ) -> dict:
        """Return usable credentials, refreshing and persisting them if needed."""
        ...

    def to_injected_inputs(self, credentials: dict) -> dict[str, str]:
        """Map credentials to the inputs injected into an agent runner call."""
        ...
