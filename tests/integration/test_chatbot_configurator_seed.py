"""Integration tests for the Chatbot Configurator seed — PrestaShop agent + connection surfacing."""

import uuid
from collections.abc import Callable, Coroutine

from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from ai_shop_helper_backend.core.seed import _seed_chatbot_configurator
from ai_shop_helper_backend.models.agent_runs import AgentInput, AgentStep, InputScope
from ai_shop_helper_backend.models.connections import ConnectionType
from ai_shop_helper_backend.models.orgs import Org
from ai_shop_helper_backend.models.project_types import ProjectType
from ai_shop_helper_backend.models.projects import Project
from ai_shop_helper_backend.models.users import User
from ai_shop_helper_backend.services import agents as agents_service
from ai_shop_helper_backend.services import connections as conn_service


async def _prestashop_project_type(session: AsyncSession, author: User) -> ProjectType:
    pt = ProjectType(name="PrestaShop", created_by=author.id, updated_by=author.id)
    session.add(pt)
    await session.flush()
    return pt


class TestChatbotConfiguratorSeed:
    async def test_seeds_agent_step_and_config_inputs(
        self,
        session: AsyncSession,
        create_user: Callable[..., Coroutine[None, None, User]],
    ) -> None:
        superuser = await create_user(email="seed-su@example.com", is_superuser=True)
        await _prestashop_project_type(session, superuser)

        await _seed_chatbot_configurator(session, superuser)
        await session.commit()

        agent = await agents_service.get_agent_by_name(session, "Chatbot Configurator")
        assert agent is not None

        step = (
            await session.exec(select(AgentStep).where(AgentStep.agent_id == agent.id))
        ).one()
        assert step.slug == "configure"
        assert step.connection_type == ConnectionType.prestashop
        assert step.token_cost == 0
        assert step.runner_ref == "chatbot_configure"

        inputs = (
            await session.exec(
                select(AgentInput).where(AgentInput.agent_id == agent.id)
            )
        ).all()
        assert {i.key for i in inputs} == {
            "chatbot_greeting",
            "chatbot_title",
            "chatbot_subtitle",
            "chatbot_color",
            "chatbot_position",
            "chatbot_teaser_text",
        }
        assert all(i.scope == InputScope.project for i in inputs)
        position = next(i for i in inputs if i.key == "chatbot_position")
        assert position.options == ["right", "left"]

    async def test_prestashop_connection_surfaces_for_project(
        self,
        session: AsyncSession,
        create_user: Callable[..., Coroutine[None, None, User]],
    ) -> None:
        superuser = await create_user(email="surface-su@example.com", is_superuser=True)
        project_type = await _prestashop_project_type(session, superuser)

        await _seed_chatbot_configurator(session, superuser)

        org = Org(
            name=f"org-{uuid.uuid4()}", created_by=superuser.id, updated_by=superuser.id
        )
        session.add(org)
        await session.flush()
        project = Project(
            org_id=org.id,
            name=f"project-{uuid.uuid4()}",
            project_type_id=project_type.id,
            created_by=superuser.id,
            updated_by=superuser.id,
        )
        session.add(project)
        await session.flush()
        await session.commit()

        relevant = await conn_service.get_relevant_connection_types(session, project)
        assert ConnectionType.prestashop in relevant

    async def test_idempotent(
        self,
        session: AsyncSession,
        create_user: Callable[..., Coroutine[None, None, User]],
    ) -> None:
        superuser = await create_user(email="idem-su@example.com", is_superuser=True)
        await _prestashop_project_type(session, superuser)

        await _seed_chatbot_configurator(session, superuser)
        await session.commit()
        await _seed_chatbot_configurator(session, superuser)
        await session.commit()

        agent = await agents_service.get_agent_by_name(session, "Chatbot Configurator")
        assert agent is not None
        steps = (
            await session.exec(select(AgentStep).where(AgentStep.agent_id == agent.id))
        ).all()
        assert len(steps) == 1
        inputs = (
            await session.exec(
                select(AgentInput).where(AgentInput.agent_id == agent.id)
            )
        ).all()
        assert len(inputs) == 6
