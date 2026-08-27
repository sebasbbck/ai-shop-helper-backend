"""Unit tests for itemized per-step credit charges (services/agent_runs._debit_step)
and the seed charge reconcile (core/seed._reconcile_step_charges). DB mocked."""

import uuid
from collections.abc import Callable
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException

from ai_shop_helper_backend.core.seed import _reconcile_step_charges
from ai_shop_helper_backend.models.agent_runs import AgentStepCharge
from ai_shop_helper_backend.models.orgs import Org
from ai_shop_helper_backend.services.agent_runs import _debit_step

_DEBIT = "ai_shop_helper_backend.services.agent_runs.billing.debit_credits"
_GET_ORG = "ai_shop_helper_backend.services.agent_runs._get_run_org"


def _exec_result(all_: Any = None, first_: Any = None) -> MagicMock:
    result = MagicMock()
    result.all.return_value = all_ or []
    result.first.return_value = first_
    return result


def _run() -> SimpleNamespace:
    return SimpleNamespace(
        id=uuid.uuid4(), credits_debited=0, debited_sub=0, debited_purchased=0
    )


class TestDebitStepItemized:
    async def test_one_debit_per_charge_with_labels(
        self, mock_session: AsyncMock, make_org: Callable[..., Org]
    ) -> None:
        """Each charge produces its own labeled debit; run totals accumulate to the sum."""
        step_id = uuid.uuid4()
        charges = [
            AgentStepCharge(step_id=step_id, order=0, reason="article", credits=35),
            AgentStepCharge(step_id=step_id, order=1, reason="image", credits=50),
            AgentStepCharge(step_id=step_id, order=2, reason="wp_upload", credits=2),
        ]
        mock_session.exec.return_value = _exec_result(all_=charges)
        org = make_org(subscription_credits=1000, purchased_credits=0)
        run = _run()
        step = SimpleNamespace(id=step_id, slug="generate")

        async def _debit(_s: Any, _o: Any, amount: int, **_: Any) -> tuple[int, int]:
            return amount, 0

        with (
            patch(_GET_ORG, AsyncMock(return_value=org)),
            patch(_DEBIT, AsyncMock(side_effect=_debit)) as debit,
        ):
            await _debit_step(mock_session, run, step)

        assert debit.await_count == 3
        assert [c.args[2] for c in debit.await_args_list] == [35, 50, 2]
        assert [c.kwargs["reason"] for c in debit.await_args_list] == [
            "article",
            "image",
            "wp_upload",
        ]
        assert run.credits_debited == 87
        assert run.debited_sub == 87
        assert run.debited_purchased == 0

    async def test_insufficient_balance_is_all_or_nothing(
        self, mock_session: AsyncMock, make_org: Callable[..., Org]
    ) -> None:
        """If the org can't cover the step total, raise 402 and debit nothing."""
        step_id = uuid.uuid4()
        charges = [
            AgentStepCharge(step_id=step_id, order=0, reason="article", credits=35),
            AgentStepCharge(step_id=step_id, order=1, reason="image", credits=50),
        ]
        mock_session.exec.return_value = _exec_result(all_=charges)
        org = make_org(subscription_credits=10, purchased_credits=0)
        run = _run()
        step = SimpleNamespace(id=step_id, slug="generate")

        with (
            patch(_GET_ORG, AsyncMock(return_value=org)),
            patch(_DEBIT, AsyncMock()) as debit,
        ):
            with pytest.raises(HTTPException) as exc:
                await _debit_step(mock_session, run, step)

        assert exc.value.status_code == 402
        debit.assert_not_awaited()
        assert run.credits_debited == 0

    async def test_no_charges_is_free(self, mock_session: AsyncMock) -> None:
        """A step with no charge rows debits nothing and never loads the org."""
        mock_session.exec.return_value = _exec_result(all_=[])
        run = _run()
        step = SimpleNamespace(id=uuid.uuid4(), slug="titles")

        with (
            patch(_GET_ORG, AsyncMock()) as get_org,
            patch(_DEBIT, AsyncMock()) as debit,
        ):
            await _debit_step(mock_session, run, step)

        get_org.assert_not_awaited()
        debit.assert_not_awaited()
        assert run.credits_debited == 0


class TestReconcileStepCharges:
    async def test_creates_missing_charges_and_sets_token_cost(
        self, mock_session: AsyncMock
    ) -> None:
        """Absent charges are inserted; token_cost becomes their sum."""
        mock_session.exec.return_value = _exec_result(first_=None)
        step = SimpleNamespace(id=uuid.uuid4(), token_cost=0)

        await _reconcile_step_charges(
            mock_session, step, [("article", 35), ("image", 50)]
        )

        assert step.token_cost == 85
        added = [
            c.args[0]
            for c in mock_session.add.call_args_list
            if isinstance(c.args[0], AgentStepCharge)
        ]
        assert {(a.reason, a.credits, a.order) for a in added} == {
            ("article", 35, 0),
            ("image", 50, 1),
        }

    async def test_updates_existing_charge_in_place(
        self, mock_session: AsyncMock
    ) -> None:
        """An existing charge is updated (credits + order), not duplicated."""
        existing = AgentStepCharge(
            step_id=uuid.uuid4(), order=9, reason="article", credits=1
        )
        mock_session.exec.return_value = _exec_result(first_=existing)
        step = SimpleNamespace(id=uuid.uuid4(), token_cost=0)

        await _reconcile_step_charges(mock_session, step, [("article", 35)])

        assert step.token_cost == 35
        assert existing.credits == 35
        assert existing.order == 0
