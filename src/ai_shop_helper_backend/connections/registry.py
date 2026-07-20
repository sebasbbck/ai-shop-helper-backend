from ai_shop_helper_backend.connections.base import ConnectionProvider
from ai_shop_helper_backend.connections.wordpress import WordpressProvider
from ai_shop_helper_backend.models.connections import ConnectionType

_registry: dict[ConnectionType, ConnectionProvider] = {
    ConnectionType.wordpress: WordpressProvider(),
}


def get_connection_provider(connection_type: ConnectionType) -> ConnectionProvider:
    provider = _registry.get(connection_type)
    if provider is None:
        raise ValueError(
            f"No connection provider registered for type: {connection_type!r}"
        )
    return provider
