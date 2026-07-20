from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status
from sqlmodel.ext.asyncio.session import AsyncSession

from ai_shop_helper_backend.core.callback_token import verify_callback_token
from ai_shop_helper_backend.core.constants import (
    PROJECT_CONTEXT_FIELDS,
    PROJECT_CONTEXT_KEYS,
)
from ai_shop_helper_backend.core.deps import CurrentUser, SessionDep
from ai_shop_helper_backend.models.agent_runs import AgentRun
from ai_shop_helper_backend.models.projects import Project
from ai_shop_helper_backend.models.users import User
from ai_shop_helper_backend.schemas.agent_runs import (
    AgentInputSchema,
    AgentRunPublic,
    AgentRunStepPublic,
    AgentSchemaResponse,
    AgentStepSchema,
    CallbackBody,
    CallbackResponse,
    CreateRunBody,
    ProjectContextFieldSchema,
    ProjectContextPut,
    ProjectContextResponse,
    SubmitRunInputsBody,
)
from ai_shop_helper_backend.services import agent_runs as svc
from ai_shop_helper_backend.services import org_users
from ai_shop_helper_backend.services.projects import get_project_by_id

router = APIRouter(tags=["agent-runs"])


async def _require_project_member(
    session: AsyncSession, current_user: User, project_id: UUID
) -> Project:
    project = await get_project_by_id(session, project_id)
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Project not found"
        )
    membership = await org_users.get_org_user(session, current_user.id, project.org_id)
    if not membership and not current_user.is_superuser:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not a member of this organization",
        )
    return project


async def _require_run_project_member(
    session: AsyncSession, current_user: User, run_id: UUID
) -> AgentRun:
    run = await session.get(AgentRun, run_id)
    if not run:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Run not found"
        )
    await _require_project_member(session, current_user, run.project_id)
    return run


@router.get(
    "/projects/{project_id}/agents/{agent_id}/schema",
    response_model=AgentSchemaResponse,
)
async def get_agent_schema(
    project_id: UUID,
    agent_id: UUID,
    current_user: CurrentUser,
    session: SessionDep,
) -> AgentSchemaResponse:
    await _require_project_member(session, current_user, project_id)
    raw = await svc.get_agent_schema(session, agent_id)
    steps_out = []
    for entry in raw["steps"]:
        step = entry["step"]
        inputs_out = [AgentInputSchema.model_validate(ai) for ai in entry["inputs"]]
        steps_out.append(
            AgentStepSchema(
                id=step.id,
                order=step.order,
                slug=step.slug,
                inputs=inputs_out,
            )
        )
    return AgentSchemaResponse(agent_id=agent_id, steps=steps_out)


def _context_fields() -> list[ProjectContextFieldSchema]:
    return [
        ProjectContextFieldSchema(
            key=f.key,
            input_type=f.input_type,
            required=f.required,
            label_i18n_key=f.label_i18n_key,
        )
        for f in PROJECT_CONTEXT_FIELDS
    ]


@router.get("/projects/{project_id}/context", response_model=ProjectContextResponse)
async def get_project_context(
    project_id: UUID,
    current_user: CurrentUser,
    session: SessionDep,
) -> ProjectContextResponse:
    await _require_project_member(session, current_user, project_id)
    rows = await svc.get_project_agent_inputs(session, project_id)
    values = {r.input_key: r.value for r in rows if r.input_key in PROJECT_CONTEXT_KEYS}
    return ProjectContextResponse(
        project_id=project_id, fields=_context_fields(), values=values
    )


@router.put("/projects/{project_id}/context", response_model=ProjectContextResponse)
async def put_project_context(
    project_id: UUID,
    body: ProjectContextPut,
    current_user: CurrentUser,
    session: SessionDep,
) -> ProjectContextResponse:
    await _require_project_member(session, current_user, project_id)
    accepted = {k: v for k, v in body.values.items() if k in PROJECT_CONTEXT_KEYS}
    await svc.set_project_agent_inputs(session, project_id, accepted, current_user.id)
    await session.commit()
    rows = await svc.get_project_agent_inputs(session, project_id)
    values = {r.input_key: r.value for r in rows if r.input_key in PROJECT_CONTEXT_KEYS}
    return ProjectContextResponse(
        project_id=project_id, fields=_context_fields(), values=values
    )


@router.post(
    "/projects/{project_id}/agents/{agent_id}/runs",
    response_model=AgentRunPublic,
    status_code=status.HTTP_201_CREATED,
)
async def create_run(
    project_id: UUID,
    agent_id: UUID,
    body: CreateRunBody,
    current_user: CurrentUser,
    session: SessionDep,
) -> AgentRunPublic:
    await _require_project_member(session, current_user, project_id)
    run = await svc.create_run(
        session, project_id, agent_id, body.run_inputs, current_user
    )
    steps = await svc.get_run_steps(session, run.id)
    return AgentRunPublic(
        **run.model_dump(),
        steps=[AgentRunStepPublic.model_validate(s) for s in steps],
    )


@router.get("/agent-runs/{run_id}", response_model=AgentRunPublic)
async def get_run(
    run_id: UUID,
    current_user: CurrentUser,
    session: SessionDep,
) -> AgentRunPublic:
    run = await _require_run_project_member(session, current_user, run_id)
    steps = await svc.get_run_steps(session, run.id)
    return AgentRunPublic(
        **run.model_dump(),
        steps=[AgentRunStepPublic.model_validate(s) for s in steps],
    )


@router.post("/agent-runs/{run_id}/inputs", response_model=AgentRunPublic)
async def submit_run_inputs(
    run_id: UUID,
    body: SubmitRunInputsBody,
    current_user: CurrentUser,
    session: SessionDep,
) -> AgentRunPublic:
    await _require_run_project_member(session, current_user, run_id)
    run = await svc.submit_run_inputs(session, run_id, body.inputs, current_user)
    steps = await svc.get_run_steps(session, run.id)
    return AgentRunPublic(
        **run.model_dump(),
        steps=[AgentRunStepPublic.model_validate(s) for s in steps],
    )


@router.get("/projects/{project_id}/agent-runs", response_model=list[AgentRunPublic])
async def list_project_runs(
    project_id: UUID,
    current_user: CurrentUser,
    session: SessionDep,
) -> list[AgentRunPublic]:
    await _require_project_member(session, current_user, project_id)
    runs = await svc.list_project_runs(session, project_id)
    result = []
    for run in runs:
        steps = await svc.get_run_steps(session, run.id)
        result.append(
            AgentRunPublic(
                **run.model_dump(),
                steps=[AgentRunStepPublic.model_validate(s) for s in steps],
            )
        )
    return result


@router.post(
    "/agent-runs/{run_id}/steps/{step_id}/callback",
    response_model=CallbackResponse,
)
async def step_callback(
    run_id: UUID,
    step_id: UUID,
    body: CallbackBody,
    session: SessionDep,
    token: str = Query(...),
) -> CallbackResponse:
    if not verify_callback_token(run_id, step_id, token):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid callback token",
        )
    await svc.record_step_result(
        session,
        run_id=run_id,
        step_id=step_id,
        success=body.success,
        data=body.data,
        error=body.error,
    )
    return CallbackResponse(status="ok")
