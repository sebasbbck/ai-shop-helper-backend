from datetime import UTC, datetime
from uuid import UUID

from fastapi import HTTPException, status
from sqlmodel import col, select
from sqlmodel.ext.asyncio.session import AsyncSession

from ai_shop_helper_backend.connections.registry import get_connection_provider
from ai_shop_helper_backend.core.callback_token import make_callback_token
from ai_shop_helper_backend.core.config import settings
from ai_shop_helper_backend.core.constants import (
    PROJECT_CONTEXT_FIELDS,
    NotificationType,
)
from ai_shop_helper_backend.models.agent_runs import (
    AgentInput,
    AgentRun,
    AgentRunStep,
    AgentStep,
    AgentStepCharge,
    InputScope,
    ProjectAgentInput,
    RunStatus,
)
from ai_shop_helper_backend.models.orgs import Org
from ai_shop_helper_backend.models.projects import Project
from ai_shop_helper_backend.models.users import User
from ai_shop_helper_backend.runners.base import StartResult
from ai_shop_helper_backend.runners.registry import get_runner
from ai_shop_helper_backend.services import billing
from ai_shop_helper_backend.services import connections as conn_service
from ai_shop_helper_backend.services import notifications as notifications_service
from ai_shop_helper_backend.services.orgs import get_org_by_id
from ai_shop_helper_backend.services.projects import get_project_by_id


async def _verify_project_membership(
    session: AsyncSession, user: User, project_id: UUID
) -> None:
    from ai_shop_helper_backend.services import org_users

    project = await get_project_by_id(session, project_id)
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Project not found"
        )
    membership = await org_users.get_org_user(session, user.id, project.org_id)
    if not membership and not user.is_superuser:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not a member of this organization",
        )


async def _get_steps_ordered(session: AsyncSession, agent_id: UUID) -> list[AgentStep]:
    result = await session.exec(
        select(AgentStep)
        .where(AgentStep.agent_id == agent_id)
        .order_by(col(AgentStep.order))
    )
    return list(result.all())


async def _get_inputs_for_agent(
    session: AsyncSession, agent_id: UUID
) -> list[AgentInput]:
    result = await session.exec(
        select(AgentInput)
        .where(AgentInput.agent_id == agent_id)
        .order_by(col(AgentInput.order))
    )
    return list(result.all())


async def _get_project_agent_inputs_map(
    session: AsyncSession, project_id: UUID
) -> dict[str, str]:
    result = await session.exec(
        select(ProjectAgentInput).where(ProjectAgentInput.project_id == project_id)
    )
    return {row.input_key: row.value for row in result.all()}


async def _get_connection_injected_inputs(
    session: AsyncSession, project_id: UUID, step: AgentStep
) -> dict[str, str]:
    if step.connection_type is None:
        return {}
    connection = await conn_service.get_connection_by_project_and_type(
        session, project_id, step.connection_type
    )
    if not connection:
        return {}
    provider = get_connection_provider(step.connection_type)
    credentials = await provider.get_credentials(session, connection)
    return provider.to_injected_inputs(credentials)


async def _resolve_inputs_for_step(
    session: AsyncSession,
    step: AgentStep,
    project_id: UUID,
    run_inputs_so_far: dict[str, str],
    prior_outputs: dict[str, str],
) -> dict[str, str]:
    project_answers = await _get_project_agent_inputs_map(session, project_id)
    resolved: dict[str, str] = {}
    resolved.update(project_answers)
    resolved.update(prior_outputs)
    resolved.update(run_inputs_so_far)
    return resolved


def _collect_run_inputs_so_far(run_steps: list[AgentRunStep]) -> dict[str, str]:
    collected: dict[str, str] = {}
    for rs in run_steps:
        for k, v in rs.input_snapshot.items():
            if isinstance(v, str):
                collected[k] = v
    return collected


def _collect_prior_outputs(run_steps: list[AgentRunStep]) -> dict[str, str]:
    outputs: dict[str, str] = {}
    for rs in run_steps:
        if rs.output:
            for k, v in rs.output.items():
                if isinstance(v, str):
                    outputs[k] = v
    return outputs


def _build_callback_url(run_id: UUID, step_id: UUID) -> str:
    token = make_callback_token(run_id, step_id)
    return (
        f"{settings.BACKEND_URL}"
        f"/agent-runs/{run_id}/steps/{step_id}/callback"
        f"?token={token}"
    )


async def _get_step_charges(
    session: AsyncSession, step: AgentStep
) -> list[AgentStepCharge]:
    result = await session.exec(
        select(AgentStepCharge)
        .where(AgentStepCharge.step_id == step.id)
        .order_by(col(AgentStepCharge.order))
    )
    return [c for c in result.all() if c.credits > 0]


async def _debit_step(session: AsyncSession, run: AgentRun, step: AgentStep) -> None:
    charges = await _get_step_charges(session, step)
    if not charges:
        return

    org = await _get_run_org(session, run)
    if org is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Organization not found"
        )

    total = sum(c.credits for c in charges)
    if org.subscription_credits + org.purchased_credits < total:
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED, detail="Insufficient credits"
        )

    for charge in charges:
        from_sub, from_pur = await billing.debit_credits(
            session,
            org,
            charge.credits,
            reason=charge.reason,
            meta={"run_id": str(run.id), "step": step.slug},
        )
        run.credits_debited += charge.credits
        run.debited_sub += from_sub
        run.debited_purchased += from_pur
    session.add(run)


async def _start_step(
    session: AsyncSession,
    run: AgentRun,
    step: AgentStep,
    run_step: AgentRunStep,
    run_inputs_so_far: dict[str, str],
) -> None:
    await _debit_step(session, run, step)

    prior_run_steps_result = await session.exec(
        select(AgentRunStep)
        .where(AgentRunStep.run_id == run.id)
        .where(AgentRunStep.status == RunStatus.success)
    )
    prior_run_steps = list(prior_run_steps_result.all())
    prior_outputs = _collect_prior_outputs(prior_run_steps)

    resolved = await _resolve_inputs_for_step(
        session, step, run.project_id, run_inputs_so_far, prior_outputs
    )

    run_step.status = RunStatus.running
    run_step.input_snapshot = resolved
    run_step.started_at = datetime.now(UTC)
    session.add(run_step)

    injected = await _get_connection_injected_inputs(session, run.project_id, step)
    outbound = {**resolved, **injected}

    callback_url = _build_callback_url(run.id, run_step.id)

    result: StartResult = await get_runner(step.runner_type).start(
        runner_ref=step.runner_ref,
        inputs=outbound,
        task_id=str(run_step.id),
        callback_url=callback_url,
    )

    if not result.accepted:
        run_step.status = RunStatus.failed
        run_step.error = result.error or "Runner rejected start"
        run_step.finished_at = datetime.now(UTC)
        session.add(run_step)

        run.status = RunStatus.failed
        run.error = run_step.error
        run.finished_at = datetime.now(UTC)
        session.add(run)

        org = await _get_run_org(session, run)
        if org and (run.debited_sub or run.debited_purchased):
            await billing.refund_credits(
                session,
                org,
                run.debited_sub,
                run.debited_purchased,
                reason=billing.REASON_REFUND,
                meta={"run_id": str(run.id)},
            )
        await _notify_run_finished(session, run, False, org.id if org else None)
        return

    if result.sync_output is not None:
        run_step.output = result.sync_output
        run_step.status = RunStatus.success
        run_step.finished_at = datetime.now(UTC)
        session.add(run_step)
        await _advance_run(session, run, step, run_step, run_inputs_so_far)


async def _notify_run_finished(
    session: AsyncSession, run: AgentRun, success: bool, org_id: UUID | None
) -> None:
    await notifications_service.create_notification(
        session,
        run.created_by,
        NotificationType.EXECUTION_FINISHED,
        org_id=org_id,
        payload={
            "reason": "success" if success else "failed",
            "run_id": str(run.id),
            "project_id": str(run.project_id),
        },
    )


async def _get_run_org(session: AsyncSession, run: AgentRun) -> Org | None:
    project = await get_project_by_id(session, run.project_id)
    if not project:
        return None
    return await get_org_by_id(session, project.org_id)


async def _advance_run(
    session: AsyncSession,
    run: AgentRun,
    completed_step: AgentStep,
    completed_run_step: AgentRunStep,
    run_inputs_so_far: dict[str, str],
) -> None:
    all_steps = await _get_steps_ordered(session, run.agent_id)
    next_step = next((s for s in all_steps if s.order > completed_step.order), None)

    if next_step is None:
        run.status = RunStatus.success
        run.finished_at = datetime.now(UTC)
        session.add(run)
        await _notify_run_finished(session, run, True, org_id=None)
        return

    agent_inputs = await _get_inputs_for_agent(session, run.agent_id)
    next_step_run_inputs = [
        ai
        for ai in agent_inputs
        if ai.step_id == next_step.id and ai.scope == InputScope.run
    ]

    merged_run_inputs = dict(run_inputs_so_far)
    if completed_run_step.input_snapshot:
        for k, v in completed_run_step.input_snapshot.items():
            if isinstance(v, str) and k not in merged_run_inputs:
                merged_run_inputs[k] = v

    missing = [ai.key for ai in next_step_run_inputs if ai.key not in merged_run_inputs]

    next_run_step = AgentRunStep(
        run_id=run.id,
        step_id=next_step.id,
        status=RunStatus.pending,
        input_snapshot={},
    )
    session.add(next_run_step)
    await session.flush()
    await session.refresh(next_run_step)

    if missing:
        run.status = RunStatus.awaiting_input
        run.current_step_order = next_step.order
        next_run_step.status = RunStatus.pending
        session.add(run)
        session.add(next_run_step)
        return

    run.current_step_order = next_step.order
    session.add(run)
    await _start_step(session, run, next_step, next_run_step, merged_run_inputs)


async def get_agent_schema(session: AsyncSession, agent_id: UUID) -> dict:
    steps = await _get_steps_ordered(session, agent_id)
    inputs = await _get_inputs_for_agent(session, agent_id)

    inputs_by_step: dict[UUID | None, list[AgentInput]] = {}
    for ai in inputs:
        inputs_by_step.setdefault(ai.step_id, []).append(ai)

    agent_level_inputs = inputs_by_step.get(None, [])

    result_steps = []
    for index, step in enumerate(steps):
        step_inputs = list(inputs_by_step.get(step.id, []))
        if index == 0:
            step_inputs = agent_level_inputs + step_inputs
        result_steps.append({"step": step, "inputs": step_inputs})

    return {"agent_id": agent_id, "steps": result_steps}


async def get_project_agent_inputs(
    session: AsyncSession, project_id: UUID
) -> list[ProjectAgentInput]:
    result = await session.exec(
        select(ProjectAgentInput).where(ProjectAgentInput.project_id == project_id)
    )
    return list(result.all())


async def set_project_agent_inputs(
    session: AsyncSession,
    project_id: UUID,
    values: dict[str, str],
    author_id: UUID,
) -> list[ProjectAgentInput]:
    existing_result = await session.exec(
        select(ProjectAgentInput).where(ProjectAgentInput.project_id == project_id)
    )
    existing_map = {row.input_key: row for row in existing_result.all()}

    rows = []
    for key, value in values.items():
        if key in existing_map:
            existing = existing_map[key]
            existing.value = value
            session.add(existing)
            rows.append(existing)
        else:
            row = ProjectAgentInput(
                project_id=project_id,
                input_key=key,
                value=value,
            )
            session.add(row)
            rows.append(row)

    await session.flush()
    for row in rows:
        await session.refresh(row)
    return rows


async def _validate_run_preconditions(
    session: AsyncSession,
    project: Project,
    agent_id: UUID,
    first_step: AgentStep,
    run_inputs: dict[str, str],
) -> None:
    steps = await _get_steps_ordered(session, agent_id)
    needed_types = {s.connection_type for s in steps if s.connection_type is not None}
    for connection_type in needed_types:
        connection = await conn_service.get_connection_by_project_and_type(
            session, project.id, connection_type
        )
        if not connection:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT, detail="connection_required"
            )

    context_values = await _get_project_agent_inputs_map(session, project.id)
    missing: list[str] = [
        f.key
        for f in PROJECT_CONTEXT_FIELDS
        if f.required and not context_values.get(f.key)
    ]
    if missing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"missing_context:{','.join(missing)}",
        )

    inputs = await _get_inputs_for_agent(session, agent_id)
    run_missing: list[str] = [
        ai.key
        for ai in inputs
        if ai.required
        and ai.scope == InputScope.run
        and ai.step_id in (first_step.id, None)
        and not run_inputs.get(ai.key)
    ]
    if run_missing:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"missing_inputs:{','.join(run_missing)}",
        )


async def create_run(
    session: AsyncSession,
    project_id: UUID,
    agent_id: UUID,
    run_inputs: dict[str, str],
    author: User,
) -> AgentRun:
    project = await get_project_by_id(session, project_id)
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Project not found"
        )

    steps = await _get_steps_ordered(session, agent_id)
    if not steps:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Agent has no steps",
        )

    first_step = steps[0]
    await _validate_run_preconditions(
        session, project, agent_id, first_step, run_inputs
    )

    run = AgentRun(
        project_id=project_id,
        agent_id=agent_id,
        status=RunStatus.running,
        current_step_order=first_step.order,
        credits_debited=0,
        debited_sub=0,
        debited_purchased=0,
        created_by=author.id,
    )
    session.add(run)
    await session.flush()
    await session.refresh(run)

    first_run_step = AgentRunStep(
        run_id=run.id,
        step_id=first_step.id,
        status=RunStatus.pending,
        input_snapshot={},
    )
    session.add(first_run_step)
    await session.flush()
    await session.refresh(first_run_step)

    await _start_step(session, run, first_step, first_run_step, run_inputs)

    await session.commit()
    await session.refresh(run)
    return run


async def record_step_result(
    session: AsyncSession,
    run_id: UUID,
    step_id: UUID,
    success: bool,
    data: dict | None,
    error: str | None,
) -> None:
    run_step_result = await session.exec(
        select(AgentRunStep)
        .where(AgentRunStep.id == step_id)
        .where(AgentRunStep.run_id == run_id)
    )
    run_step = run_step_result.first()
    if not run_step:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Run step not found"
        )

    if run_step.status != RunStatus.running:
        return

    run_result = await session.exec(select(AgentRun).where(AgentRun.id == run_id))
    run = run_result.first()
    if not run:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Run not found"
        )

    if not success:
        run_step.status = RunStatus.failed
        run_step.error = error
        run_step.finished_at = datetime.now(UTC)
        session.add(run_step)

        run.status = RunStatus.failed
        run.error = error
        run.finished_at = datetime.now(UTC)
        session.add(run)

        org = await _get_run_org(session, run)
        if org and (run.debited_sub or run.debited_purchased):
            await billing.refund_credits(
                session,
                org,
                run.debited_sub,
                run.debited_purchased,
                reason=billing.REASON_REFUND,
                meta={"run_id": str(run_id)},
            )
        await _notify_run_finished(session, run, False, org.id if org else None)

        await session.commit()
        return

    run_step.output = data
    run_step.status = RunStatus.success
    run_step.finished_at = datetime.now(UTC)
    session.add(run_step)

    completed_step = await session.get(AgentStep, run_step.step_id)
    if not completed_step:
        await session.commit()
        return

    all_started_steps_result = await session.exec(
        select(AgentRunStep).where(AgentRunStep.run_id == run_id)
    )
    all_run_steps = list(all_started_steps_result.all())
    run_inputs_so_far: dict[str, str] = {}
    for rs in all_run_steps:
        for k, v in rs.input_snapshot.items():
            if isinstance(v, str):
                run_inputs_so_far[k] = v

    await _advance_run(session, run, completed_step, run_step, run_inputs_so_far)
    await session.commit()


async def submit_run_inputs(
    session: AsyncSession,
    run_id: UUID,
    inputs: dict[str, str],
    author: User,
) -> AgentRun:
    run_result = await session.exec(select(AgentRun).where(AgentRun.id == run_id))
    run = run_result.first()
    if not run:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Run not found"
        )

    if run.status != RunStatus.awaiting_input:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Run is not awaiting input",
        )

    all_steps = await _get_steps_ordered(session, run.agent_id)
    awaited_step = next(
        (s for s in all_steps if s.order == run.current_step_order), None
    )
    if not awaited_step:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Could not determine awaited step",
        )

    awaited_run_step_result = await session.exec(
        select(AgentRunStep)
        .where(AgentRunStep.run_id == run_id)
        .where(AgentRunStep.step_id == awaited_step.id)
        .where(AgentRunStep.status == RunStatus.pending)
    )
    awaited_run_step = awaited_run_step_result.first()
    if not awaited_run_step:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Awaited run step not found",
        )

    all_run_steps_result = await session.exec(
        select(AgentRunStep).where(AgentRunStep.run_id == run_id)
    )
    all_run_steps = list(all_run_steps_result.all())
    run_inputs_so_far = _collect_run_inputs_so_far(all_run_steps)
    run_inputs_so_far.update(inputs)

    run.status = RunStatus.running
    session.add(run)

    await _start_step(session, run, awaited_step, awaited_run_step, run_inputs_so_far)
    await session.commit()
    await session.refresh(run)
    return run


async def get_run(session: AsyncSession, run_id: UUID) -> AgentRun | None:
    return await session.get(AgentRun, run_id)


async def get_run_steps(session: AsyncSession, run_id: UUID) -> list[AgentRunStep]:
    result = await session.exec(
        select(AgentRunStep)
        .where(AgentRunStep.run_id == run_id)
        .order_by(col(AgentRunStep.started_at))
    )
    return list(result.all())


async def list_project_runs(session: AsyncSession, project_id: UUID) -> list[AgentRun]:
    result = await session.exec(
        select(AgentRun)
        .where(AgentRun.project_id == project_id)
        .order_by(col(AgentRun.created_at).desc())
    )
    return list(result.all())
