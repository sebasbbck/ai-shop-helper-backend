"""Unit tests for stripe_gateway.seed_products price-sync (path A). Stripe SDK mocked."""

from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

from ai_shop_helper_backend.core.constants import SubscriptionTier
from ai_shop_helper_backend.services import stripe_gateway

_STRIPE = "ai_shop_helper_backend.services.stripe_gateway.stripe"
_TIERS = "ai_shop_helper_backend.services.stripe_gateway.SUBSCRIPTION_TIERS"

PRO = [SubscriptionTier("pro", "Pro", 2500, 2000)]


def _stripe_mock(tier_list: Any) -> MagicMock:
    m = MagicMock()
    topup = SimpleNamespace(data=[object()])
    m.Price.list_async = AsyncMock(side_effect=[tier_list, topup])
    m.Product.create_async = AsyncMock(return_value=SimpleNamespace(id="prod_new"))
    m.Price.create_async = AsyncMock()
    m.Price.modify_async = AsyncMock()
    return m


class TestSeedProductsPriceSync:
    async def test_changed_price_transfers_key_and_archives_old(self) -> None:
        """A tier whose amount changed → new price with transferred key, old archived, product reused."""
        existing = SimpleNamespace(id="price_old", unit_amount=5900, product="prod_old")
        m = _stripe_mock(SimpleNamespace(data=[existing]))

        with patch(_STRIPE, m), patch(_TIERS, PRO):
            await stripe_gateway.seed_products()

        m.Product.create_async.assert_not_awaited()
        m.Price.create_async.assert_awaited_once()
        kw = m.Price.create_async.await_args.kwargs
        assert kw["product"] == "prod_old"
        assert kw["unit_amount"] == 2000
        assert kw["lookup_key"] == "aish_pro"
        assert kw["transfer_lookup_key"] is True
        m.Price.modify_async.assert_awaited_once_with("price_old", active=False)

    async def test_new_tier_creates_product_and_price(self) -> None:
        """A tier with no existing price → create product + price, no transfer, no archive."""
        m = _stripe_mock(SimpleNamespace(data=[]))

        with patch(_STRIPE, m), patch(_TIERS, PRO):
            await stripe_gateway.seed_products()

        m.Product.create_async.assert_awaited_once()
        m.Price.create_async.assert_awaited_once()
        kw = m.Price.create_async.await_args.kwargs
        assert kw["product"] == "prod_new"
        assert kw["unit_amount"] == 2000
        assert "transfer_lookup_key" not in kw
        m.Price.modify_async.assert_not_awaited()

    async def test_up_to_date_price_is_left_untouched(self) -> None:
        """A tier whose price already matches → no create, no archive."""
        existing = SimpleNamespace(id="price_ok", unit_amount=2000, product="prod_ok")
        m = _stripe_mock(SimpleNamespace(data=[existing]))

        with patch(_STRIPE, m), patch(_TIERS, PRO):
            await stripe_gateway.seed_products()

        m.Product.create_async.assert_not_awaited()
        m.Price.create_async.assert_not_awaited()
        m.Price.modify_async.assert_not_awaited()
