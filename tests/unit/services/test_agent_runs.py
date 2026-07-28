"""Unit tests for services/agent_runs.py and core/callback_token.py."""

import uuid
from collections.abc import Callable
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from ai_shop_helper_backend.core.callback_token import (
    make_callback_token,
    verify_callback_token,
)
from ai_shop_helper_backend.models.agent_runs import (
    AgentInput,
    AgentRun,
    AgentRunStep,
    AgentStep,
    InputScope,
    InputType,
    RunnerType,
    RunStatus,
)
from ai_shop_helper_backend.models.connections import ConnectionType
from ai_shop_helper_backend.models.orgs import Org
from ai_shop_helper_backend.models.users import User


def _make_step(
    agent_id: uuid.UUID,
    order: int = 1,
    slug: str = "step1",
    runner_ref: str = "wf_ref",
    token_cost: int = 10,
    step_id: uuid.UUID | None = None,
    connection_type: ConnectionType | None = None,
) -> AgentStep:
    return AgentStep(
        id=step_id or uuid.uuid4(),
        agent_id=agent_id,
        order=order,
        slug=slug,
        runner_type=RunnerType.n8n,
        runner_ref=runner_ref,
        token_cost=token_cost,
        connection_type=connection_type,
    )


def _make_run(
    project_id: uuid.UUID,
    agent_id: uuid.UUID,
    status: RunStatus = RunStatus.running,
    credits_debited: int = 10,
    current_step_order: int = 1,
    run_id: uuid.UUID | None = None,
    created_by: uuid.UUID | None = None,
    debited_sub: int | None = None,
    debited_purchased: int = 0,
) -> AgentRun:
    return AgentRun(
        id=run_id or uuid.uuid4(),
        project_id=project_id,
        agent_id=agent_id,
        status=status,
        current_step_order=current_step_order,
        credits_debited=credits_debited,
        debited_sub=credits_debited if debited_sub is None else debited_sub,
        debited_purchased=debited_purchased,
        created_by=created_by or uuid.uuid4(),
        created_at=datetime.now(UTC),
    )


def _make_run_step(
    run_id: uuid.UUID,
    step_id: uuid.UUID,
    status: RunStatus = RunStatus.running,
    input_snapshot: dict | None = None,
    output: dict | None = None,
    runstep_id: uuid.UUID | None = None,
) -> AgentRunStep:
    return AgentRunStep(
        id=runstep_id or uuid.uuid4(),
        run_id=run_id,
        step_id=step_id,
        status=status,
        input_snapshot=input_snapshot or {},
        output=output,
    )


class TestCallbackToken:
    def test_make_and_verify_roundtrip(self) -> None:
        run_id = uuid.uuid4()
        step_id = uuid.uuid4()
        token = make_callback_token(run_id, step_id)
        assert verify_callback_token(run_id, step_id, token) is True

    def test_wrong_run_id_fails(self) -> None:
        run_id = uuid.uuid4()
        step_id = uuid.uuid4()
        token = make_callback_token(run_id, step_id)
        assert verify_callback_token(uuid.uuid4(), step_id, token) is False

    def test_wrong_step_id_fails(self) -> None:
        run_id = uuid.uuid4()
        step_id = uuid.uuid4()
        token = make_callback_token(run_id, step_id)
        assert verify_callback_token(run_id, uuid.uuid4(), token) is False

    def test_tampered_token_fails(self) -> None:
        run_id = uuid.uuid4()
        step_id = uuid.uuid4()
        token = make_callback_token(run_id, step_id)
        bad_token = token[:-4] + "aaaa"
        assert verify_callback_token(run_id, step_id, bad_token) is False

    def test_tokens_differ_per_step(self) -> None:
        run_id = uuid.uuid4()
        t1 = make_callback_token(run_id, uuid.uuid4())
        t2 = make_callback_token(run_id, uuid.uuid4())
        assert t1 != t2


class TestCreateRun:
    async def test_debits_and_starts_step1_runner_accepted(
        self,
        mock_session: AsyncMock,
        make_org: Callable[..., Org],
        make_user: Callable[..., User],
    ) -> None:
        from ai_shop_helper_backend.runners.base import StartResult
        from ai_shop_helper_backend.services.agent_runs import create_run

        project_id = uuid.uuid4()
        agent_id = uuid.uuid4()
        org = make_org(subscription_credits=100, purchased_credits=0)
        user = make_user()

        step1 = _make_step(agent_id, order=1, token_cost=10)
        run = _make_run(project_id, agent_id, credits_debited=10)
        run_step = _make_run_step(run.id, step1.id)

        accepted_result = StartResult(
            accepted=True,
            status_code=200,
            sync_output=None,
            external_ref=str(run_step.id),
            error=None,
        )

        with (
            patch(
                "ai_shop_helper_backend.services.agent_runs.get_project_by_id",
                return_value=MagicMock(org_id=org.id),
            ),
            patch(
                "ai_shop_helper_backend.services.agent_runs.get_org_by_id",
                return_value=org,
            ),
            patch(
                "ai_shop_helper_backend.services.agent_runs.billing.debit_credits",
                new_callable=AsyncMock,
                return_value=(10, 0),
            ) as mock_debit,
            patch(
                "ai_shop_helper_backend.services.agent_runs._get_steps_ordered",
                new_callable=AsyncMock,
                return_value=[step1],
            ),
            patch(
                "ai_shop_helper_backend.services.agent_runs._get_inputs_for_agent",
                new_callable=AsyncMock,
                return_value=[],
            ),
            patch(
                "ai_shop_helper_backend.services.agent_runs._get_project_agent_inputs_map",
                new_callable=AsyncMock,
                return_value={},
            ),
            patch(
                "ai_shop_helper_backend.services.agent_runs._get_connection_injected_inputs",
                new_callable=AsyncMock,
                return_value={},
            ),
            patch(
                "ai_shop_helper_backend.services.agent_runs._validate_run_preconditions",
                new_callable=AsyncMock,
                return_value=None,
            ),
            patch(
                "ai_shop_helper_backend.services.agent_runs.get_runner",
                return_value=MagicMock(start=AsyncMock(return_value=accepted_result)),
            ),
        ):
            mock_session.flush = AsyncMock()
            mock_session.refresh = AsyncMock(side_effect=[run, run_step, run])
            mock_session.commit = AsyncMock()
            mock_session.exec = AsyncMock(
                return_value=MagicMock(all=MagicMock(return_value=[]))
            )

            await create_run(mock_session, project_id, agent_id, {}, user)

        mock_debit.assert_awaited_once()
        debit_call = mock_debit.call_args
        assert debit_call.args[2] == 10

    async def test_injected_creds_reach_runner_but_not_snapshot(
        self,
        mock_session: AsyncMock,
        make_org: Callable[..., Org],
        make_user: Callable[..., User],
    ) -> None:
        from ai_shop_helper_backend.runners.base import StartResult
        from ai_shop_helper_backend.services.agent_runs import create_run

        project_id = uuid.uuid4()
        agent_id = uuid.uuid4()
        org = make_org(subscription_credits=100, purchased_credits=0)
        user = make_user()

        step1 = _make_step(agent_id, order=1, token_cost=10)
        run = _make_run(project_id, agent_id, credits_debited=10)
        run_step = _make_run_step(run.id, step1.id)

        accepted_result = StartResult(
            accepted=True,
            status_code=200,
            sync_output=None,
            external_ref=str(run_step.id),
            error=None,
        )
        runner_mock = MagicMock(start=AsyncMock(return_value=accepted_result))

        with (
            patch(
                "ai_shop_helper_backend.services.agent_runs.get_project_by_id",
                return_value=MagicMock(org_id=org.id),
            ),
            patch(
                "ai_shop_helper_backend.services.agent_runs.get_org_by_id",
                return_value=org,
            ),
            patch(
                "ai_shop_helper_backend.services.agent_runs.billing.debit_credits",
                new_callable=AsyncMock,
                return_value=(10, 0),
            ),
            patch(
                "ai_shop_helper_backend.services.agent_runs._get_steps_ordered",
                new_callable=AsyncMock,
                return_value=[step1],
            ),
            patch(
                "ai_shop_helper_backend.services.agent_runs._get_inputs_for_agent",
                new_callable=AsyncMock,
                return_value=[],
            ),
            patch(
                "ai_shop_helper_backend.services.agent_runs._get_project_agent_inputs_map",
                new_callable=AsyncMock,
                return_value={"business": "shoes"},
            ),
            patch(
                "ai_shop_helper_backend.services.agent_runs._get_connection_injected_inputs",
                new_callable=AsyncMock,
                return_value={"url": "https://wp.example", "auth_token": "SECRET"},
            ),
            patch(
                "ai_shop_helper_backend.services.agent_runs._validate_run_preconditions",
                new_callable=AsyncMock,
                return_value=None,
            ),
            patch(
                "ai_shop_helper_backend.services.agent_runs.get_runner",
                return_value=runner_mock,
            ),
        ):
            mock_session.flush = AsyncMock()
            mock_session.refresh = AsyncMock(side_effect=[run, run_step, run])
            mock_session.commit = AsyncMock()
            mock_session.exec = AsyncMock(
                return_value=MagicMock(all=MagicMock(return_value=[]))
            )

            await create_run(mock_session, project_id, agent_id, {}, user)

        sent_inputs = runner_mock.start.call_args.kwargs["inputs"]
        assert sent_inputs["auth_token"] == "SECRET"
        assert sent_inputs["url"] == "https://wp.example"
        assert sent_inputs["business"] == "shoes"

        added_steps = [
            c.args[0]
            for c in mock_session.add.call_args_list
            if isinstance(c.args[0], AgentRunStep)
        ]
        snapshot = added_steps[0].input_snapshot
        assert "auth_token" not in snapshot
        assert "url" not in snapshot
        assert snapshot["business"] == "shoes"

    async def test_insufficient_credits_propagates_402(
        self,
        mock_session: AsyncMock,
        make_org: Callable[..., Org],
        make_user: Callable[..., User],
    ) -> None:
        from fastapi import HTTPException

        from ai_shop_helper_backend.services.agent_runs import create_run

        project_id = uuid.uuid4()
        agent_id = uuid.uuid4()
        org = make_org(subscription_credits=0, purchased_credits=0)
        user = make_user()
        step1 = _make_step(agent_id, order=1, token_cost=10)

        with (
            patch(
                "ai_shop_helper_backend.services.agent_runs.get_project_by_id",
                return_value=MagicMock(org_id=org.id),
            ),
            patch(
                "ai_shop_helper_backend.services.agent_runs.get_org_by_id",
                return_value=org,
            ),
            patch(
                "ai_shop_helper_backend.services.agent_runs._get_steps_ordered",
                new_callable=AsyncMock,
                return_value=[step1],
            ),
            patch(
                "ai_shop_helper_backend.services.agent_runs._validate_run_preconditions",
                new_callable=AsyncMock,
                return_value=None,
            ),
            patch(
                "ai_shop_helper_backend.services.agent_runs.billing.debit_credits",
                new_callable=AsyncMock,
                side_effect=HTTPException(
                    status_code=402, detail="Insufficient credits"
                ),
            ),
        ):
            with pytest.raises(HTTPException) as exc_info:
                await create_run(mock_session, project_id, agent_id, {}, user)

        assert exc_info.value.status_code == 402

    async def test_runner_rejected_refunds_credits(
        self,
        mock_session: AsyncMock,
        make_org: Callable[..., Org],
        make_user: Callable[..., User],
    ) -> None:
        from ai_shop_helper_backend.runners.base import StartResult
        from ai_shop_helper_backend.services.agent_runs import create_run

        project_id = uuid.uuid4()
        agent_id = uuid.uuid4()
        org = make_org(subscription_credits=100)
        user = make_user()
        step1 = _make_step(agent_id, order=1, token_cost=10)
        run = _make_run(project_id, agent_id, credits_debited=10)
        run_step = _make_run_step(run.id, step1.id)

        rejected_result = StartResult(
            accepted=False,
            status_code=500,
            sync_output=None,
            external_ref=None,
            error="runner error",
        )

        with (
            patch(
                "ai_shop_helper_backend.services.agent_runs.get_project_by_id",
                return_value=MagicMock(org_id=org.id),
            ),
            patch(
                "ai_shop_helper_backend.services.agent_runs.get_org_by_id",
                return_value=org,
            ),
            patch(
                "ai_shop_helper_backend.services.agent_runs.billing.debit_credits",
                new_callable=AsyncMock,
                return_value=(10, 0),
            ),
            patch(
                "ai_shop_helper_backend.services.agent_runs.billing.refund_credits",
                new_callable=AsyncMock,
            ) as mock_refund,
            patch(
                "ai_shop_helper_backend.services.agent_runs._get_steps_ordered",
                new_callable=AsyncMock,
                return_value=[step1],
            ),
            patch(
                "ai_shop_helper_backend.services.agent_runs._get_inputs_for_agent",
                new_callable=AsyncMock,
                return_value=[],
            ),
            patch(
                "ai_shop_helper_backend.services.agent_runs._get_project_agent_inputs_map",
                new_callable=AsyncMock,
                return_value={},
            ),
            patch(
                "ai_shop_helper_backend.services.agent_runs._get_connection_injected_inputs",
                new_callable=AsyncMock,
                return_value={},
            ),
            patch(
                "ai_shop_helper_backend.services.agent_runs._validate_run_preconditions",
                new_callable=AsyncMock,
                return_value=None,
            ),
            patch(
                "ai_shop_helper_backend.services.agent_runs.get_runner",
                return_value=MagicMock(start=AsyncMock(return_value=rejected_result)),
            ),
            patch(
                "ai_shop_helper_backend.services.agent_runs._get_run_org",
                new_callable=AsyncMock,
                return_value=org,
            ),
        ):
            mock_session.flush = AsyncMock()
            mock_session.refresh = AsyncMock(side_effect=[run, run_step, run])
            mock_session.commit = AsyncMock()
            mock_session.exec = AsyncMock(
                return_value=MagicMock(all=MagicMock(return_value=[]))
            )

            result = await create_run(mock_session, project_id, agent_id, {}, user)

        mock_refund.assert_awaited_once()
        assert result.status == RunStatus.failed


class TestRecordStepResult:
    async def test_success_callback_advances_to_success_when_last_step(
        self,
        mock_session: AsyncMock,
        make_org: Callable[..., Org],
    ) -> None:
        from ai_shop_helper_backend.services.agent_runs import record_step_result

        agent_id = uuid.uuid4()
        project_id = uuid.uuid4()
        step1 = _make_step(agent_id, order=1)
        run = _make_run(project_id, agent_id, credits_debited=10)
        run_step = _make_run_step(run.id, step1.id, status=RunStatus.running)

        with (
            patch(
                "ai_shop_helper_backend.services.agent_runs._get_steps_ordered",
                new_callable=AsyncMock,
                return_value=[step1],
            ),
            patch(
                "ai_shop_helper_backend.services.agent_runs._get_inputs_for_agent",
                new_callable=AsyncMock,
                return_value=[],
            ),
            patch(
                "ai_shop_helper_backend.services.agent_runs._get_project_agent_inputs_map",
                new_callable=AsyncMock,
                return_value={},
            ),
            patch(
                "ai_shop_helper_backend.services.agent_runs._get_connection_injected_inputs",
                new_callable=AsyncMock,
                return_value={},
            ),
            patch(
                "ai_shop_helper_backend.services.agent_runs._validate_run_preconditions",
                new_callable=AsyncMock,
                return_value=None,
            ),
        ):
            exec_results = [
                MagicMock(first=MagicMock(return_value=run_step)),
                MagicMock(first=MagicMock(return_value=run)),
                MagicMock(all=MagicMock(return_value=[run_step])),
            ]
            mock_session.exec = AsyncMock(side_effect=exec_results)
            mock_session.get = AsyncMock(return_value=step1)
            mock_session.commit = AsyncMock()

            await record_step_result(
                mock_session,
                run_id=run.id,
                step_id=run_step.id,
                success=True,
                data={"output_key": "val"},
                error=None,
            )

        assert run_step.status == RunStatus.success
        assert run_step.output == {"output_key": "val"}
        assert run.status == RunStatus.success

    async def test_failure_callback_marks_run_failed_and_refunds(
        self,
        mock_session: AsyncMock,
        make_org: Callable[..., Org],
    ) -> None:
        from ai_shop_helper_backend.services.agent_runs import record_step_result

        org = make_org(subscription_credits=0, purchased_credits=50)
        agent_id = uuid.uuid4()
        project_id = uuid.uuid4()
        step1 = _make_step(agent_id, order=1)
        run = _make_run(project_id, agent_id, credits_debited=10)
        run_step = _make_run_step(run.id, step1.id, status=RunStatus.running)

        exec_results = [
            MagicMock(first=MagicMock(return_value=run_step)),
            MagicMock(first=MagicMock(return_value=run)),
        ]
        mock_session.exec = AsyncMock(side_effect=exec_results)
        mock_session.commit = AsyncMock()

        with (
            patch(
                "ai_shop_helper_backend.services.agent_runs._get_run_org",
                new_callable=AsyncMock,
                return_value=org,
            ),
            patch(
                "ai_shop_helper_backend.services.agent_runs.billing.refund_credits",
                new_callable=AsyncMock,
            ) as mock_refund,
        ):
            await record_step_result(
                mock_session,
                run_id=run.id,
                step_id=run_step.id,
                success=False,
                data=None,
                error="step failed",
            )

        assert run_step.status == RunStatus.failed
        assert run.status == RunStatus.failed
        mock_refund.assert_awaited_once()
        refund_call = mock_refund.call_args
        assert refund_call.args[2] == 10

    async def test_callback_idempotent_when_step_already_success(
        self,
        mock_session: AsyncMock,
    ) -> None:
        from ai_shop_helper_backend.services.agent_runs import record_step_result

        agent_id = uuid.uuid4()
        project_id = uuid.uuid4()
        step1 = _make_step(agent_id, order=1)
        run = _make_run(project_id, agent_id)
        run_step = _make_run_step(run.id, step1.id, status=RunStatus.success)

        mock_session.exec = AsyncMock(
            side_effect=[
                MagicMock(first=MagicMock(return_value=run_step)),
            ]
        )

        await record_step_result(
            mock_session,
            run_id=run.id,
            step_id=run_step.id,
            success=True,
            data={"x": 1},
            error=None,
        )

        mock_session.commit.assert_not_awaited()

    async def test_success_advances_to_awaiting_input_when_run_inputs_missing(
        self,
        mock_session: AsyncMock,
    ) -> None:
        from ai_shop_helper_backend.services.agent_runs import record_step_result

        agent_id = uuid.uuid4()
        project_id = uuid.uuid4()
        step1 = _make_step(agent_id, order=1, slug="titles")
        step2 = _make_step(agent_id, order=2, slug="generate", step_id=uuid.uuid4())

        run = _make_run(project_id, agent_id, credits_debited=20, current_step_order=1)
        run_step1 = _make_run_step(run.id, step1.id, status=RunStatus.running)

        run_input = AgentInput(
            id=uuid.uuid4(),
            agent_id=agent_id,
            step_id=step2.id,
            key="chosen_title",
            input_type=InputType.select,
            scope=InputScope.run,
            order=1,
            required=True,
            label_i18n_key="choose_title",
        )

        new_run_step2 = _make_run_step(run.id, step2.id, status=RunStatus.pending)

        with (
            patch(
                "ai_shop_helper_backend.services.agent_runs._get_steps_ordered",
                new_callable=AsyncMock,
                return_value=[step1, step2],
            ),
            patch(
                "ai_shop_helper_backend.services.agent_runs._get_inputs_for_agent",
                new_callable=AsyncMock,
                return_value=[run_input],
            ),
            patch(
                "ai_shop_helper_backend.services.agent_runs._get_project_agent_inputs_map",
                new_callable=AsyncMock,
                return_value={},
            ),
            patch(
                "ai_shop_helper_backend.services.agent_runs._get_connection_injected_inputs",
                new_callable=AsyncMock,
                return_value={},
            ),
            patch(
                "ai_shop_helper_backend.services.agent_runs._validate_run_preconditions",
                new_callable=AsyncMock,
                return_value=None,
            ),
        ):
            flush_count = 0

            async def flush_side_effect():
                nonlocal flush_count
                flush_count += 1

            async def refresh_side_effect(obj):
                if isinstance(obj, AgentRunStep):
                    obj.id = new_run_step2.id

            exec_results = [
                MagicMock(first=MagicMock(return_value=run_step1)),
                MagicMock(first=MagicMock(return_value=run)),
                MagicMock(all=MagicMock(return_value=[run_step1])),
            ]
            mock_session.exec = AsyncMock(side_effect=exec_results)
            mock_session.get = AsyncMock(return_value=step1)
            mock_session.flush = AsyncMock(side_effect=flush_side_effect)
            mock_session.refresh = AsyncMock(side_effect=refresh_side_effect)
            mock_session.commit = AsyncMock()

            await record_step_result(
                mock_session,
                run_id=run.id,
                step_id=run_step1.id,
                success=True,
                data={"titles": ["A", "B"]},
                error=None,
            )

        assert run.status == RunStatus.awaiting_input
        assert run.current_step_order == 2


class TestSubmitRunInputs:
    async def test_submit_inputs_starts_next_step(
        self,
        mock_session: AsyncMock,
        make_user: Callable[..., User],
    ) -> None:
        from ai_shop_helper_backend.runners.base import StartResult
        from ai_shop_helper_backend.services.agent_runs import submit_run_inputs

        user = make_user()
        agent_id = uuid.uuid4()
        project_id = uuid.uuid4()
        step2 = _make_step(agent_id, order=2, slug="generate")
        run = _make_run(
            project_id, agent_id, status=RunStatus.awaiting_input, current_step_order=2
        )
        pending_run_step2 = _make_run_step(run.id, step2.id, status=RunStatus.pending)

        accepted = StartResult(
            accepted=True,
            status_code=200,
            sync_output=None,
            external_ref=str(pending_run_step2.id),
            error=None,
        )

        with (
            patch(
                "ai_shop_helper_backend.services.agent_runs._get_steps_ordered",
                new_callable=AsyncMock,
                return_value=[step2],
            ),
            patch(
                "ai_shop_helper_backend.services.agent_runs._get_inputs_for_agent",
                new_callable=AsyncMock,
                return_value=[],
            ),
            patch(
                "ai_shop_helper_backend.services.agent_runs._get_project_agent_inputs_map",
                new_callable=AsyncMock,
                return_value={},
            ),
            patch(
                "ai_shop_helper_backend.services.agent_runs._get_connection_injected_inputs",
                new_callable=AsyncMock,
                return_value={},
            ),
            patch(
                "ai_shop_helper_backend.services.agent_runs._validate_run_preconditions",
                new_callable=AsyncMock,
                return_value=None,
            ),
            patch(
                "ai_shop_helper_backend.services.agent_runs._debit_step",
                new_callable=AsyncMock,
                return_value=None,
            ),
            patch(
                "ai_shop_helper_backend.services.agent_runs.get_runner",
                return_value=MagicMock(start=AsyncMock(return_value=accepted)),
            ),
        ):
            exec_results = [
                MagicMock(first=MagicMock(return_value=run)),
                MagicMock(first=MagicMock(return_value=pending_run_step2)),
                MagicMock(all=MagicMock(return_value=[pending_run_step2])),
                MagicMock(all=MagicMock(return_value=[])),
            ]
            mock_session.exec = AsyncMock(side_effect=exec_results)
            mock_session.commit = AsyncMock()
            mock_session.flush = AsyncMock()
            mock_session.refresh = AsyncMock(return_value=None)
            mock_session.get = AsyncMock(return_value=run)

            result = await submit_run_inputs(
                mock_session, run.id, {"chosen_title": "My Title"}, user
            )

        assert result.status == RunStatus.running

    async def test_submit_inputs_rejects_when_not_awaiting(
        self,
        mock_session: AsyncMock,
        make_user: Callable[..., User],
    ) -> None:
        from fastapi import HTTPException

        from ai_shop_helper_backend.services.agent_runs import submit_run_inputs

        user = make_user()
        agent_id = uuid.uuid4()
        project_id = uuid.uuid4()
        run = _make_run(project_id, agent_id, status=RunStatus.running)

        mock_session.exec = AsyncMock(
            return_value=MagicMock(first=MagicMock(return_value=run))
        )

        with pytest.raises(HTTPException) as exc_info:
            await submit_run_inputs(mock_session, run.id, {"key": "val"}, user)

        assert exc_info.value.status_code == 409


class TestCallbackTokenEndpoint:
    def test_bad_token_returns_false(self) -> None:
        run_id = uuid.uuid4()
        step_id = uuid.uuid4()
        assert verify_callback_token(run_id, step_id, "bad_token") is False

    def test_correct_token_returns_true(self) -> None:
        run_id = uuid.uuid4()
        step_id = uuid.uuid4()
        token = make_callback_token(run_id, step_id)
        assert verify_callback_token(run_id, step_id, token) is True


class TestSyncOutput:
    async def test_sync_output_immediately_recorded(
        self,
        mock_session: AsyncMock,
        make_org: Callable[..., Org],
        make_user: Callable[..., User],
    ) -> None:
        from ai_shop_helper_backend.runners.base import StartResult
        from ai_shop_helper_backend.services.agent_runs import create_run

        org = make_org(subscription_credits=100)
        user = make_user()
        agent_id = uuid.uuid4()
        project_id = uuid.uuid4()
        step1 = _make_step(agent_id, order=1, token_cost=10)
        run = _make_run(project_id, agent_id, credits_debited=10)
        run_step = _make_run_step(run.id, step1.id)

        sync_data = {"title": "My Blog Post"}
        sync_result = StartResult(
            accepted=True,
            status_code=200,
            sync_output=sync_data,
            external_ref=str(run_step.id),
            error=None,
        )

        with (
            patch(
                "ai_shop_helper_backend.services.agent_runs.get_project_by_id",
                return_value=MagicMock(org_id=org.id),
            ),
            patch(
                "ai_shop_helper_backend.services.agent_runs.get_org_by_id",
                return_value=org,
            ),
            patch(
                "ai_shop_helper_backend.services.agent_runs.billing.debit_credits",
                new_callable=AsyncMock,
                return_value=(10, 0),
            ),
            patch(
                "ai_shop_helper_backend.services.agent_runs._get_steps_ordered",
                new_callable=AsyncMock,
                return_value=[step1],
            ),
            patch(
                "ai_shop_helper_backend.services.agent_runs._get_inputs_for_agent",
                new_callable=AsyncMock,
                return_value=[],
            ),
            patch(
                "ai_shop_helper_backend.services.agent_runs._get_project_agent_inputs_map",
                new_callable=AsyncMock,
                return_value={},
            ),
            patch(
                "ai_shop_helper_backend.services.agent_runs._get_connection_injected_inputs",
                new_callable=AsyncMock,
                return_value={},
            ),
            patch(
                "ai_shop_helper_backend.services.agent_runs._validate_run_preconditions",
                new_callable=AsyncMock,
                return_value=None,
            ),
            patch(
                "ai_shop_helper_backend.services.agent_runs.get_runner",
                return_value=MagicMock(start=AsyncMock(return_value=sync_result)),
            ),
        ):
            mock_session.flush = AsyncMock()
            mock_session.refresh = AsyncMock(side_effect=[run, run_step, run])
            mock_session.commit = AsyncMock()
            mock_session.exec = AsyncMock(
                return_value=MagicMock(all=MagicMock(return_value=[]))
            )

            await create_run(mock_session, project_id, agent_id, {}, user)

        added_run_steps = [
            c.args[0]
            for c in mock_session.add.call_args_list
            if isinstance(c.args[0], AgentRunStep)
        ]
        added_runs = [
            c.args[0]
            for c in mock_session.add.call_args_list
            if isinstance(c.args[0], AgentRun)
        ]
        assert any(rs.output == sync_data for rs in added_run_steps)
        assert any(rs.status == RunStatus.success for rs in added_run_steps)
        assert any(r.status == RunStatus.success for r in added_runs)


class TestRunPreconditions:
    def _input(self, key, scope, required=True, step_id=None):
        return AgentInput(
            agent_id=uuid.uuid4(),
            step_id=step_id,
            key=key,
            input_type=InputType.textarea,
            options=None,
            options_from_step_slug=None,
            scope=scope,
            order=1,
            required=required,
            label_i18n_key=f"AgentInputs.{key}.label",
        )

    async def test_connection_required_when_missing(
        self, mock_session: AsyncMock
    ) -> None:
        from fastapi import HTTPException

        from ai_shop_helper_backend.services.agent_runs import (
            _validate_run_preconditions,
        )

        project = MagicMock(id=uuid.uuid4(), project_type_id=uuid.uuid4())
        agent_id = uuid.uuid4()
        first_step = _make_step(
            agent_id, order=1, connection_type=ConnectionType.wordpress
        )

        with (
            patch(
                "ai_shop_helper_backend.services.agent_runs._get_steps_ordered",
                new_callable=AsyncMock,
                return_value=[first_step],
            ),
            patch(
                "ai_shop_helper_backend.services.agent_runs.conn_service.get_connection_by_project_and_type",
                new_callable=AsyncMock,
                return_value=None,
            ),
        ):
            with pytest.raises(HTTPException) as exc:
                await _validate_run_preconditions(
                    mock_session, project, agent_id, first_step, {}
                )
        assert exc.value.status_code == 409
        assert exc.value.detail == "connection_required"

    async def test_missing_required_project_context(
        self, mock_session: AsyncMock
    ) -> None:
        from fastapi import HTTPException

        from ai_shop_helper_backend.services.agent_runs import (
            _validate_run_preconditions,
        )

        project = MagicMock(id=uuid.uuid4(), project_type_id=uuid.uuid4())
        agent_id = uuid.uuid4()
        first_step = _make_step(agent_id, order=1)

        with (
            patch(
                "ai_shop_helper_backend.services.agent_runs._get_steps_ordered",
                new_callable=AsyncMock,
                return_value=[first_step],
            ),
            patch(
                "ai_shop_helper_backend.services.agent_runs._get_project_agent_inputs_map",
                new_callable=AsyncMock,
                return_value={},
            ),
        ):
            with pytest.raises(HTTPException) as exc:
                await _validate_run_preconditions(
                    mock_session, project, agent_id, first_step, {}
                )
        assert exc.value.status_code == 409
        assert exc.value.detail.startswith("missing_context:")
        assert "business" in exc.value.detail
        assert "audience" in exc.value.detail

    async def test_passes_when_satisfied(self, mock_session: AsyncMock) -> None:
        from ai_shop_helper_backend.services.agent_runs import (
            _validate_run_preconditions,
        )

        project = MagicMock(id=uuid.uuid4(), project_type_id=uuid.uuid4())
        agent_id = uuid.uuid4()
        first_step = _make_step(agent_id, order=1)

        with (
            patch(
                "ai_shop_helper_backend.services.agent_runs._get_steps_ordered",
                new_callable=AsyncMock,
                return_value=[first_step],
            ),
            patch(
                "ai_shop_helper_backend.services.agent_runs._get_inputs_for_agent",
                new_callable=AsyncMock,
                return_value=[],
            ),
            patch(
                "ai_shop_helper_backend.services.agent_runs._get_project_agent_inputs_map",
                new_callable=AsyncMock,
                return_value={"business": "shoes", "audience": "runners"},
            ),
        ):
            await _validate_run_preconditions(
                mock_session, project, agent_id, first_step, {}
            )

    async def test_create_run_rejects_before_debit(
        self,
        mock_session: AsyncMock,
        make_user: Callable[..., User],
    ) -> None:
        from fastapi import HTTPException

        from ai_shop_helper_backend.services.agent_runs import create_run

        project_id = uuid.uuid4()
        agent_id = uuid.uuid4()
        user = make_user()
        step1 = _make_step(agent_id, order=1, token_cost=10)

        with (
            patch(
                "ai_shop_helper_backend.services.agent_runs.get_project_by_id",
                new_callable=AsyncMock,
                return_value=MagicMock(project_type_id=uuid.uuid4()),
            ),
            patch(
                "ai_shop_helper_backend.services.agent_runs._get_steps_ordered",
                new_callable=AsyncMock,
                return_value=[step1],
            ),
            patch(
                "ai_shop_helper_backend.services.agent_runs._validate_run_preconditions",
                new_callable=AsyncMock,
                side_effect=HTTPException(
                    status_code=409, detail="connection_required"
                ),
            ),
            patch(
                "ai_shop_helper_backend.services.agent_runs.billing.debit_credits",
                new_callable=AsyncMock,
            ) as mock_debit,
        ):
            with pytest.raises(HTTPException) as exc:
                await create_run(mock_session, project_id, agent_id, {}, user)

        assert exc.value.status_code == 409
        mock_debit.assert_not_awaited()


class TestPerStepDebit:
    async def test_zero_cost_step_no_debit(self, mock_session: AsyncMock) -> None:
        from ai_shop_helper_backend.services.agent_runs import _debit_step

        run = _make_run(uuid.uuid4(), uuid.uuid4())
        run.credits_debited = 0
        step = _make_step(run.agent_id, order=1, token_cost=0)

        with patch(
            "ai_shop_helper_backend.services.agent_runs.billing.debit_credits",
            new_callable=AsyncMock,
        ) as mock_debit:
            await _debit_step(mock_session, run, step)

        mock_debit.assert_not_awaited()
        assert run.credits_debited == 0

    async def test_step_debits_and_accumulates_split(
        self, mock_session: AsyncMock, make_org: Callable[..., Org]
    ) -> None:
        from ai_shop_helper_backend.services.agent_runs import _debit_step

        org = make_org(subscription_credits=100, purchased_credits=100)
        run = _make_run(uuid.uuid4(), uuid.uuid4())
        run.credits_debited = 0
        run.debited_sub = 0
        run.debited_purchased = 0
        step = _make_step(run.agent_id, order=2, token_cost=5)

        with (
            patch(
                "ai_shop_helper_backend.services.agent_runs._get_run_org",
                new_callable=AsyncMock,
                return_value=org,
            ),
            patch(
                "ai_shop_helper_backend.services.agent_runs.billing.debit_credits",
                new_callable=AsyncMock,
                return_value=(3, 2),
            ) as mock_debit,
        ):
            await _debit_step(mock_session, run, step)

        mock_debit.assert_awaited_once()
        assert mock_debit.call_args.args[2] == 5
        assert run.credits_debited == 5
        assert run.debited_sub == 3
        assert run.debited_purchased == 2


class TestGetAgentSchema:
    async def test_agent_level_inputs_surface_on_first_step(
        self, mock_session: AsyncMock
    ) -> None:
        from ai_shop_helper_backend.services.agent_runs import get_agent_schema

        agent_id = uuid.uuid4()
        step1 = _make_step(agent_id, order=1, slug="titles")
        step2 = _make_step(agent_id, order=2, slug="generate")

        def _inp(key, scope, step_id):
            return AgentInput(
                agent_id=agent_id,
                step_id=step_id,
                key=key,
                input_type=InputType.textarea,
                options=None,
                options_from_step_slug=None,
                scope=scope,
                order=1,
                required=True,
                label_i18n_key=f"AgentInputs.{key}.label",
            )

        business = _inp("business", InputScope.project, None)
        chosen = _inp("chosen_title", InputScope.run, step2.id)

        with (
            patch(
                "ai_shop_helper_backend.services.agent_runs._get_steps_ordered",
                new_callable=AsyncMock,
                return_value=[step1, step2],
            ),
            patch(
                "ai_shop_helper_backend.services.agent_runs._get_inputs_for_agent",
                new_callable=AsyncMock,
                return_value=[business, chosen],
            ),
        ):
            result = await get_agent_schema(mock_session, agent_id)

        step1_keys = [i.key for i in result["steps"][0]["inputs"]]
        step2_keys = [i.key for i in result["steps"][1]["inputs"]]
        assert "business" in step1_keys
        assert "chosen_title" in step2_keys
        assert "business" not in step2_keys
