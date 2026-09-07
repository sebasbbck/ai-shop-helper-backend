import json
from collections.abc import Sequence
from uuid import UUID

from sqlmodel import col, select
from sqlmodel.ext.asyncio.session import AsyncSession

from ai_shop_helper_backend.core.crypto import encrypt
from ai_shop_helper_backend.models.agent_project_types import AgentProjectType
from ai_shop_helper_backend.models.agent_runs import AgentStep
from ai_shop_helper_backend.models.agents import Agent
from ai_shop_helper_backend.models.connections import Connection, ConnectionType
from ai_shop_helper_backend.models.projects import Project
from ai_shop_helper_backend.schemas.connections import ConnectionAvailability


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


async def get_relevant_connection_types(
    session: AsyncSession, project: Project
) -> Sequence[ConnectionType]:
    """Connection types relevant to a project, derived from the agents wired to it.

    A type is relevant when some agent available for the project's project type has
    a step that needs it (`AgentStep.connection_type`) — this is what lets the
    frontend load connection cards dynamically instead of hardcoding WordPress/Google,
    and keeps Google out of projects whose agents never touch it.
    """
    result = await session.exec(
        select(col(AgentStep.connection_type))
        .join(Agent, col(Agent.id) == col(AgentStep.agent_id))
        .join(AgentProjectType, col(AgentProjectType.agent_id) == col(Agent.id))
        .where(
            col(AgentProjectType.project_type_id) == project.project_type_id,
            col(AgentStep.connection_type).is_not(None),
        )
        .distinct()
    )
    return [connection_type for connection_type in result.all() if connection_type]


async def list_connection_availability(
    session: AsyncSession, project: Project
) -> list[ConnectionAvailability]:
    """Connection types relevant to a project, each flagged with whether it's connected.

    Only relevant types are returned — a connection established for a type no
    longer used by any of the project's agents would not show up here either.
    """
    relevant_types = await get_relevant_connection_types(session, project)
    if not relevant_types:
        return []

    result = await session.exec(
        select(col(Connection.connection_type)).where(
            col(Connection.project_id) == project.id,
            col(Connection.connection_type).in_(relevant_types),
        )
    )
    connected_types = set(result.all())

    return [
        ConnectionAvailability(
            connection_type=connection_type,
            connected=connection_type in connected_types,
        )
        for connection_type in relevant_types
    ]
