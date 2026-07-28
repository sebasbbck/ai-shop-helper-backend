"""Unit tests for services/billing.py — all DB calls mocked via mock_session."""

import uuid
from collections.abc import Callable
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from ai_shop_helper_backend.models.billing import CreditTransaction
from ai_shop_helper_backend.models.orgs import Org
from ai_shop_helper_backend.services.billing import (
    BUCKET_PURCHASED,
    BUCKET_SUBSCRIPTION,
    REASON_EXPIRY,
    REASON_REFUND,
    REASON_SUBSCRIPTION_CYCLE,
    debit_credits,
    get_balance,
    grant_purchased,
    list_ledger,
    refund_credits,
    set_subscription_credits,
)


class TestGetBalance:
    """Tests for the get_balance service function."""

    async def test_delegates_to_get_org_by_id(
        self,
        mock_session: AsyncMock,
        make_org: Callable[..., Org],
    ) -> None:
        """Test that get_balance delegates to get_org_by_id and returns the result."""
        org = make_org(subscription_credits=10, purchased_credits=5)
        with patch(
            "ai_shop_helper_backend.services.billing.get_org_by_id",
            return_value=org,
        ) as mock_get:
            result = await get_balance(mock_session, org.id)

        mock_get.assert_called_once_with(mock_session, org.id)
        assert result is org

    async def test_returns_none_when_not_found(
        self,
        mock_session: AsyncMock,
    ) -> None:
        """Test that get_balance returns None when the org does not exist."""
        with patch(
            "ai_shop_helper_backend.services.billing.get_org_by_id",
            return_value=None,
        ):
            result = await get_balance(mock_session, uuid.uuid4())

        assert result is None


class TestListLedger:
    """Tests for the list_ledger service function."""

    async def test_returns_rows_and_total(
        self,
        mock_session: AsyncMock,
        make_org: Callable[..., Org],
    ) -> None:
        """Test that list_ledger executes count and paginated queries and returns them together."""
        org = make_org()
        tx = CreditTransaction(
            org_id=org.id,
            amount=100,
            bucket=BUCKET_PURCHASED,
            balance_after=100,
            reason="purchase",
        )
        count_result = MagicMock()
        count_result.one.return_value = 1
        rows_result = MagicMock()
        rows_result.all.return_value = [tx]
        mock_session.exec.side_effect = [count_result, rows_result]

        items, total = await list_ledger(mock_session, org.id, offset=0, limit=50)

        assert mock_session.exec.call_count == 2
        assert total == 1
        assert items == [tx]


class TestGrantPurchased:
    """Tests for the grant_purchased service function."""

    async def test_increments_purchased_credits_and_writes_row(
        self,
        mock_session: AsyncMock,
        make_org: Callable[..., Org],
    ) -> None:
        """Test that grant_purchased adds amount, writes one ledger row with correct fields, and calls session.add(org)."""
        org = make_org(purchased_credits=50)
        row = await grant_purchased(
            mock_session, org, amount=200, stripe_event_id="evt_abc"
        )

        assert org.purchased_credits == 250
        assert isinstance(row, CreditTransaction)
        assert row.amount == 200
        assert row.bucket == BUCKET_PURCHASED
        assert row.balance_after == 250
        assert row.reason == "purchase"
        assert row.stripe_event_id == "evt_abc"

        add_calls = mock_session.add.call_args_list
        added_objects = [c.args[0] for c in add_calls]
        assert row in added_objects
        assert org in added_objects

    async def test_metadata_serialised_as_json(
        self,
        mock_session: AsyncMock,
        make_org: Callable[..., Org],
    ) -> None:
        """Test that meta dict is JSON-serialised into metadata_json."""
        import json

        org = make_org()
        row = await grant_purchased(
            mock_session, org, amount=100, meta={"pack": "starter"}
        )

        assert row.metadata_json == json.dumps({"pack": "starter"})

    async def test_no_meta_leaves_metadata_json_none(
        self,
        mock_session: AsyncMock,
        make_org: Callable[..., Org],
    ) -> None:
        """Test that omitting meta leaves metadata_json as None."""
        org = make_org()
        row = await grant_purchased(mock_session, org, amount=100)

        assert row.metadata_json is None


class TestSetSubscriptionCredits:
    """Tests for the set_subscription_credits service function."""

    async def test_from_zero_writes_single_grant_row(
        self,
        mock_session: AsyncMock,
        make_org: Callable[..., Org],
    ) -> None:
        """Test that setting credits from 0 writes only the subscription_cycle grant row."""
        org = make_org(subscription_credits=0)
        await set_subscription_credits(
            mock_session, org, allotment=300, stripe_event_id="evt_inv1"
        )

        assert org.subscription_credits == 300
        added_txs = [
            c.args[0]
            for c in mock_session.add.call_args_list
            if isinstance(c.args[0], CreditTransaction)
        ]
        assert len(added_txs) == 1
        grant = added_txs[0]
        assert grant.reason == REASON_SUBSCRIPTION_CYCLE
        assert grant.amount == 300
        assert grant.bucket == BUCKET_SUBSCRIPTION
        assert grant.balance_after == 300
        assert grant.stripe_event_id == "evt_inv1"

    async def test_with_leftover_writes_expiry_then_grant(
        self,
        mock_session: AsyncMock,
        make_org: Callable[..., Org],
    ) -> None:
        """Test that leftover credits produce an expiry row before the grant row."""
        org = make_org(subscription_credits=50)
        await set_subscription_credits(
            mock_session, org, allotment=300, stripe_event_id="evt_inv2"
        )

        assert org.subscription_credits == 300
        txs = [
            c.args[0]
            for c in mock_session.add.call_args_list
            if isinstance(c.args[0], CreditTransaction)
        ]
        assert len(txs) == 2
        expiry, grant = txs[0], txs[1]

        assert expiry.reason == REASON_EXPIRY
        assert expiry.amount == -50
        assert expiry.bucket == BUCKET_SUBSCRIPTION
        assert expiry.balance_after == 0
        assert expiry.stripe_event_id is None

        assert grant.reason == REASON_SUBSCRIPTION_CYCLE
        assert grant.amount == 300
        assert grant.bucket == BUCKET_SUBSCRIPTION
        assert grant.balance_after == 300
        assert grant.stripe_event_id == "evt_inv2"

    async def test_session_add_called_with_org(
        self,
        mock_session: AsyncMock,
        make_org: Callable[..., Org],
    ) -> None:
        """Test that session.add is called with the org after update."""
        org = make_org(subscription_credits=0)
        await set_subscription_credits(mock_session, org, allotment=100)

        added_objects = [c.args[0] for c in mock_session.add.call_args_list]
        assert org in added_objects


class TestDebitCredits:
    """Tests for the debit_credits service function."""

    async def test_debit_within_subscription_only(
        self,
        mock_session: AsyncMock,
        make_org: Callable[..., Org],
    ) -> None:
        """Test that a debit within subscription balance only drains subscription credits."""
        org = make_org(subscription_credits=100, purchased_credits=0)
        await debit_credits(mock_session, org, amount=60)

        assert org.subscription_credits == 40
        assert org.purchased_credits == 0
        txs = [
            c.args[0]
            for c in mock_session.add.call_args_list
            if isinstance(c.args[0], CreditTransaction)
        ]
        assert len(txs) == 1
        assert txs[0].bucket == BUCKET_SUBSCRIPTION
        assert txs[0].amount == -60
        assert txs[0].balance_after == 40

    async def test_debit_spanning_both_buckets(
        self,
        mock_session: AsyncMock,
        make_org: Callable[..., Org],
    ) -> None:
        """Test that a debit spanning buckets drains subscription first then purchased."""
        org = make_org(subscription_credits=10, purchased_credits=100)
        await debit_credits(mock_session, org, amount=60)

        assert org.subscription_credits == 0
        assert org.purchased_credits == 50
        txs = [
            c.args[0]
            for c in mock_session.add.call_args_list
            if isinstance(c.args[0], CreditTransaction)
        ]
        assert len(txs) == 2
        sub_tx = next(t for t in txs if t.bucket == BUCKET_SUBSCRIPTION)
        pur_tx = next(t for t in txs if t.bucket == BUCKET_PURCHASED)
        assert sub_tx.amount == -10
        assert sub_tx.balance_after == 0
        assert pur_tx.amount == -50
        assert pur_tx.balance_after == 50

    async def test_debit_exactly_equal_to_total(
        self,
        mock_session: AsyncMock,
        make_org: Callable[..., Org],
    ) -> None:
        """Test that a debit exactly equal to the total balance succeeds and drains both buckets."""
        org = make_org(subscription_credits=30, purchased_credits=70)
        await debit_credits(mock_session, org, amount=100)

        assert org.subscription_credits == 0
        assert org.purchased_credits == 0
        txs = [
            c.args[0]
            for c in mock_session.add.call_args_list
            if isinstance(c.args[0], CreditTransaction)
        ]
        assert len(txs) == 2

    async def test_debit_insufficient_raises_402_and_no_mutation(
        self,
        mock_session: AsyncMock,
        make_org: Callable[..., Org],
    ) -> None:
        """Test that an insufficient debit raises HTTPException(402) without mutating the org."""
        from fastapi import HTTPException

        org = make_org(subscription_credits=3, purchased_credits=2)
        original_sub = org.subscription_credits
        original_pur = org.purchased_credits

        with pytest.raises(HTTPException) as exc_info:
            await debit_credits(mock_session, org, amount=6)

        assert exc_info.value.status_code == 402
        assert org.subscription_credits == original_sub
        assert org.purchased_credits == original_pur
        added_txs = [
            c.args[0]
            for c in mock_session.add.call_args_list
            if isinstance(c.args[0], CreditTransaction)
        ]
        assert added_txs == []

    async def test_session_add_called_with_org_on_success(
        self,
        mock_session: AsyncMock,
        make_org: Callable[..., Org],
    ) -> None:
        """Test that session.add is called with the org on a successful debit."""
        org = make_org(subscription_credits=50, purchased_credits=0)
        await debit_credits(mock_session, org, amount=10)

        added_objects = [c.args[0] for c in mock_session.add.call_args_list]
        assert org in added_objects

    async def test_debit_returns_bucket_split(
        self,
        mock_session: AsyncMock,
        make_org: Callable[..., Org],
    ) -> None:
        """Test that debit_credits returns the (from_sub, from_purchased) split actually taken."""
        org = make_org(subscription_credits=10, purchased_credits=100)
        split = await debit_credits(mock_session, org, amount=60)

        assert split == (10, 50)


class TestRefundCredits:
    """Tests for the refund_credits service function."""

    async def test_refund_restores_original_buckets(
        self,
        mock_session: AsyncMock,
        make_org: Callable[..., Org],
    ) -> None:
        """Test that refund_credits returns each amount to its original bucket with one row per bucket."""
        org = make_org(subscription_credits=0, purchased_credits=0)
        await refund_credits(
            mock_session, org, from_sub=10, from_pur=50, reason=REASON_REFUND
        )

        assert org.subscription_credits == 10
        assert org.purchased_credits == 50
        txs = [
            c.args[0]
            for c in mock_session.add.call_args_list
            if isinstance(c.args[0], CreditTransaction)
        ]
        assert len(txs) == 2
        sub_tx = next(t for t in txs if t.bucket == BUCKET_SUBSCRIPTION)
        pur_tx = next(t for t in txs if t.bucket == BUCKET_PURCHASED)
        assert sub_tx.amount == 10
        assert sub_tx.reason == REASON_REFUND
        assert pur_tx.amount == 50

    async def test_refund_skips_zero_buckets(
        self,
        mock_session: AsyncMock,
        make_org: Callable[..., Org],
    ) -> None:
        """Test that refund_credits writes no row for a zero bucket."""
        org = make_org(subscription_credits=5, purchased_credits=0)
        await refund_credits(mock_session, org, from_sub=10, from_pur=0)

        assert org.subscription_credits == 15
        assert org.purchased_credits == 0
        txs = [
            c.args[0]
            for c in mock_session.add.call_args_list
            if isinstance(c.args[0], CreditTransaction)
        ]
        assert len(txs) == 1
        assert txs[0].bucket == BUCKET_SUBSCRIPTION
