import json
from uuid import UUID

from sqlmodel import col, select
from sqlmodel.ext.asyncio.session import AsyncSession

from ai_shop_helper_backend.core.crypto import encrypt
from ai_shop_helper_backend.models.connections import Connection, ConnectionType


async def get_connection_by_project_and_type(
    session: AsyncSession, project_id: UUID, connection_type: ConnectionType
) -> Connection | None:
    result = await session.exec(
        select(Connection).where(
            col(Connection.project_id) == project_id,
            col(Connection.connection_type) == connection_type,
        )
    )
    return result.first()


async def upsert_connection(
    session: AsyncSession,
    project_id: UUID,
    connection_type: ConnectionType,
    secrets: dict,
) -> Connection:
    secrets_encrypted = encrypt(json.dumps(secrets))
    existing = await get_connection_by_project_and_type(
        session, project_id, connection_type
    )
    if existing:
        existing.secrets_encrypted = secrets_encrypted
        session.add(existing)
        return existing

    connection = Connection(
        project_id=project_id,
        connection_type=connection_type,
        secrets_encrypted=secrets_encrypted,
    )
    session.add(connection)
    return connection


def build_wordpress_secrets(site_url: str, username: str, app_password: str) -> dict:
    return {"site_url": site_url, "username": username, "app_password": app_password}


async def delete_connection(session: AsyncSession, connection: Connection) -> None:
    await session.delete(connection)
