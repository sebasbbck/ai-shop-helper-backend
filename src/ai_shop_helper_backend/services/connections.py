import json
from uuid import UUID

from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from ai_shop_helper_backend.core.crypto import encrypt
from ai_shop_helper_backend.models.connections import Connection, ConnectionType


async def get_connection_by_project(
    session: AsyncSession, project_id: UUID
) -> Connection | None:
    result = await session.exec(
        select(Connection).where(Connection.project_id == project_id)
    )
    return result.first()


async def upsert_connection(
    session: AsyncSession,
    project_id: UUID,
    connection_type: ConnectionType,
    secrets: dict,
) -> Connection:
    secrets_encrypted = encrypt(json.dumps(secrets))
    existing = await get_connection_by_project(session, project_id)
    if existing:
        existing.connection_type = connection_type
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
