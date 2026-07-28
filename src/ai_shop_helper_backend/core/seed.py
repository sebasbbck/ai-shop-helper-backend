from sqlalchemy.exc import IntegrityError
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from ai_shop_helper_backend.core.config import settings
from ai_shop_helper_backend.core.db import AsyncSessionLocal
from ai_shop_helper_backend.core.security import hash_password
from ai_shop_helper_backend.models.agent_project_types import AgentProjectType
from ai_shop_helper_backend.models.agent_runs import (
    AgentInput,
    AgentStep,
    InputScope,
    InputType,
    RunnerType,
)
from ai_shop_helper_backend.models.agents import Agent
from ai_shop_helper_backend.models.connections import ConnectionType
from ai_shop_helper_backend.models.project_types import ProjectType
from ai_shop_helper_backend.models.roles import Role
from ai_shop_helper_backend.models.users import User
from ai_shop_helper_backend.services import agent_project_types as apt_service
from ai_shop_helper_backend.services import agents as agents_service
from ai_shop_helper_backend.services import project_types as project_types_service
from ai_shop_helper_backend.services import roles as roles_service
from ai_shop_helper_backend.services import users as users_service

BASE_ROLES: list[tuple[str, int, str]] = [
    ("Owner", 0, "Full control of the organization."),
    ("Admin", 10, "Manage organization members and projects."),
    ("Member", 20, "Standard organization member."),
]

BASE_PROJECT_TYPES: list[str] = ["WordPress", "PrestaShop"]


async def _get_agent_step_by_slug(
    session: AsyncSession, agent_id: object, slug: str
) -> AgentStep | None:
    result = await session.exec(
        select(AgentStep).where(AgentStep.agent_id == agent_id, AgentStep.slug == slug)
    )
    return result.first()


async def _get_agent_input_by_key(
    session: AsyncSession, agent_id: object, key: str
) -> AgentInput | None:
    result = await session.exec(
        select(AgentInput).where(AgentInput.agent_id == agent_id, AgentInput.key == key)
    )
    return result.first()


async def _seed_blog_writer(session: AsyncSession, superuser: User) -> None:
    agent = await agents_service.get_agent_by_name(session, "Blog Writer")
    if agent is None:
        agent = Agent(
            name="Blog Writer",
            description="Generate SEO blog posts for your store.",
            created_by=superuser.id,
            updated_by=superuser.id,
        )
        session.add(agent)
        await session.flush()

    wp_project_type = await project_types_service.get_project_type_by_name(
        session, "WordPress"
    )
    if wp_project_type is not None and (
        await apt_service.get_agent_project_type_by_combination(
            session, agent.id, wp_project_type.id
        )
        is None
    ):
        session.add(
            AgentProjectType(
                agent_id=agent.id,
                project_type_id=wp_project_type.id,
                created_by=superuser.id,
                updated_by=superuser.id,
            )
        )

    step_titles = await _get_agent_step_by_slug(session, agent.id, "titles")
    if step_titles is None:
        step_titles = AgentStep(
            agent_id=agent.id,
            order=1,
            slug="titles",
            runner_type=RunnerType.n8n,
            runner_ref="blog_titles",
            token_cost=0,
            connection_type=ConnectionType.wordpress,
        )
        session.add(step_titles)
        await session.flush()

    step_generate = await _get_agent_step_by_slug(session, agent.id, "generate")
    if step_generate is None:
        step_generate = AgentStep(
            agent_id=agent.id,
            order=2,
            slug="generate",
            runner_type=RunnerType.n8n,
            runner_ref="blog_generate",
            token_cost=1,
            connection_type=ConnectionType.wordpress,
        )
        session.add(step_generate)
        await session.flush()

    project_inputs: list[
        tuple[str, InputType, int, str, AgentStep | None, list | None, str | None]
    ] = []
    run_inputs: list[
        tuple[str, InputType, int, str, AgentStep | None, list | None, str | None]
    ] = [
        (
            "chosen_title",
            InputType.select,
            1,
            "AgentInputs.chosen_title.label",
            step_generate,
            None,
            "titles",
        ),
        (
            "image_method",
            InputType.select,
            2,
            "AgentInputs.image_method.label",
            step_generate,
            ["ai_images"],
            None,
        ),
    ]

    for scope, specs in (
        (InputScope.project, project_inputs),
        (InputScope.run, run_inputs),
    ):
        for (
            key,
            input_type,
            order,
            label_key,
            step,
            options,
            options_from_slug,
        ) in specs:
            if await _get_agent_input_by_key(session, agent.id, key) is not None:
                continue
            session.add(
                AgentInput(
                    agent_id=agent.id,
                    step_id=step.id if step else None,
                    key=key,
                    input_type=input_type,
                    options=options,
                    options_from_step_slug=options_from_slug,
                    scope=scope,
                    order=order,
                    required=True,
                    label_i18n_key=label_key,
                )
            )


async def seed() -> None:
    """Ensure the bootstrap superuser and base roles exist.

    Idempotent: safe to run on every startup. Roles require an author (FK to
    user.id), so the superuser is created first and authors the base roles.
    """
    async with AsyncSessionLocal() as session:
        superuser = await users_service.get_user_by_email(
            session, settings.FIRST_SUPERUSER_EMAIL
        )
        if superuser is None:
            superuser = User(
                email=settings.FIRST_SUPERUSER_EMAIL,
                name="Admin",
                hashed_password=hash_password(settings.FIRST_SUPERUSER_PASSWORD),
                is_superuser=True,
                is_active=True,
                email_verified=True,
            )
            session.add(superuser)
            await session.flush()

        for name, access_level, description in BASE_ROLES:
            if await roles_service.get_role_by_name(session, name) is None:
                session.add(
                    Role(
                        name=name,
                        description=description,
                        access_level=access_level,
                        created_by=superuser.id,
                        updated_by=superuser.id,
                    )
                )

        for type_name in BASE_PROJECT_TYPES:
            existing_pt = await project_types_service.get_project_type_by_name(
                session, type_name
            )
            if existing_pt is None:
                session.add(
                    ProjectType(
                        name=type_name,
                        created_by=superuser.id,
                        updated_by=superuser.id,
                    )
                )

        await session.flush()

        await _seed_blog_writer(session, superuser)

        try:
            await session.commit()
        except IntegrityError:
            await session.rollback()

    from ai_shop_helper_backend.services import stripe_gateway

    await stripe_gateway.seed_products()
