"""Unit tests for services/referrals.py — all DB calls mocked via mock_session."""

import uuid
from collections.abc import Callable
from unittest.mock import AsyncMock, patch

from ai_shop_helper_backend.core.constants import REFERRAL_REWARD, ReferralReward
from ai_shop_helper_backend.models.orgs import Org
from ai_shop_helper_backend.models.referrals import (
    STATUS_CAPPED,
    STATUS_PENDING,
    STATUS_REWARDED,
    Referral,
    ReferralCode,
)
from ai_shop_helper_backend.services.referrals import (
    _CODE_ALPHABET,
    _CODE_LENGTH,
    _generate_code,
    _unique_code,
    count_rewarded_this_month,
    get_code_by_org,
    get_or_create_code,
    get_referral_by_referee_user,
    link_referee_org,
    list_referrals,
    on_org_paid,
    record_signup,
    resolve_code,
)

_REF = "ai_shop_helper_backend.services.referrals"


class TestGenerateCode:
    """Tests for the _generate_code helper."""

    def test_uses_safe_alphabet_and_length(self) -> None:
        """Test that generated codes match the configured length and ambiguous-free alphabet."""
        for _ in range(50):
            code = _generate_code()
            assert len(code) == _CODE_LENGTH
            assert all(c in _CODE_ALPHABET for c in code)
            assert not (set(code) & set("OI01"))


class TestQueryHelpers:
    """Tests for the thin query-wrapper functions."""

    async def test_resolve_code_returns_first_match(
        self, mock_session: AsyncMock
    ) -> None:
        """Test that resolve_code returns the first row for a raw code."""
        code = ReferralCode(org_id=uuid.uuid4(), code="ABCD2345")
        mock_session.exec.return_value.first.return_value = code

        assert await resolve_code(mock_session, "ABCD2345") is code

    async def test_get_code_by_org_returns_first(self, mock_session: AsyncMock) -> None:
        """Test that get_code_by_org returns the org's first code row."""
        code = ReferralCode(org_id=uuid.uuid4(), code="ABCD2345")
        mock_session.exec.return_value.first.return_value = code

        assert await get_code_by_org(mock_session, code.org_id) is code

    async def test_get_referral_by_referee_user_returns_first(
        self, mock_session: AsyncMock
    ) -> None:
        """Test that get_referral_by_referee_user returns the first match."""
        referral = Referral(
            referrer_org_id=uuid.uuid4(),
            referee_user_id=uuid.uuid4(),
            status=STATUS_PENDING,
        )
        mock_session.exec.return_value.first.return_value = referral

        assert (
            await get_referral_by_referee_user(mock_session, referral.referee_user_id)
            is referral
        )

    async def test_list_referrals_returns_all(self, mock_session: AsyncMock) -> None:
        """Test that list_referrals returns every row for the referrer org."""
        rows = [
            Referral(
                referrer_org_id=uuid.uuid4(),
                referee_user_id=uuid.uuid4(),
                status=STATUS_PENDING,
            )
        ]
        mock_session.exec.return_value.all.return_value = rows

        assert await list_referrals(mock_session, uuid.uuid4()) == rows

    async def test_unique_code_retries_on_collision(
        self, mock_session: AsyncMock
    ) -> None:
        """Test that _unique_code retries until it finds a free code."""
        taken = ReferralCode(org_id=uuid.uuid4(), code="TAKEN567")
        with patch(
            f"{_REF}.resolve_code", AsyncMock(side_effect=[taken, None])
        ) as resolver:
            result = await _unique_code(mock_session)

        assert result not in ("",)
        assert resolver.await_count == 2


class TestGetOrCreateCode:
    """Tests for the get_or_create_code service function."""

    async def test_returns_existing_without_creating(
        self, mock_session: AsyncMock
    ) -> None:
        """Test that an existing org code is returned and nothing is added."""
        org_id = uuid.uuid4()
        existing = ReferralCode(org_id=org_id, code="EXISTING1")
        with patch(f"{_REF}.get_code_by_org", AsyncMock(return_value=existing)):
            result = await get_or_create_code(mock_session, org_id, uuid.uuid4())

        assert result is existing
        mock_session.add.assert_not_called()

    async def test_creates_when_absent(self, mock_session: AsyncMock) -> None:
        """Test that a new code is generated, added, and attributed to the creator."""
        org_id = uuid.uuid4()
        user_id = uuid.uuid4()
        with (
            patch(f"{_REF}.get_code_by_org", AsyncMock(return_value=None)),
            patch(f"{_REF}._unique_code", AsyncMock(return_value="NEWCODE7")),
        ):
            result = await get_or_create_code(mock_session, org_id, user_id)

        assert result.org_id == org_id
        assert result.code == "NEWCODE7"
        assert result.created_by == user_id
        mock_session.add.assert_called_once_with(result)


class TestRecordSignup:
    """Tests for the record_signup service function."""

    async def test_unknown_code_is_noop(self, mock_session: AsyncMock) -> None:
        """Test that an unknown code records nothing and returns None."""
        with patch(f"{_REF}.resolve_code", AsyncMock(return_value=None)):
            result = await record_signup(mock_session, "NOPE", uuid.uuid4())

        assert result is None
        mock_session.add.assert_not_called()

    async def test_already_referred_is_noop(self, mock_session: AsyncMock) -> None:
        """Test that a user who already has a referral is not referred again."""
        code = ReferralCode(org_id=uuid.uuid4(), code="ABCD2345")
        existing = Referral(
            referrer_org_id=uuid.uuid4(),
            referee_user_id=uuid.uuid4(),
            status=STATUS_PENDING,
        )
        with (
            patch(f"{_REF}.resolve_code", AsyncMock(return_value=code)),
            patch(
                f"{_REF}.get_referral_by_referee_user",
                AsyncMock(return_value=existing),
            ),
        ):
            result = await record_signup(mock_session, "ABCD2345", uuid.uuid4())

        assert result is None
        mock_session.add.assert_not_called()

    async def test_records_pending_referral(self, mock_session: AsyncMock) -> None:
        """Test that a valid code creates a pending referral bound to the referrer org."""
        referrer_org_id = uuid.uuid4()
        referee_user_id = uuid.uuid4()
        code = ReferralCode(org_id=referrer_org_id, code="ABCD2345")
        with (
            patch(f"{_REF}.resolve_code", AsyncMock(return_value=code)),
            patch(f"{_REF}.get_referral_by_referee_user", AsyncMock(return_value=None)),
        ):
            result = await record_signup(mock_session, "ABCD2345", referee_user_id)

        assert result is not None
        assert result.referrer_org_id == referrer_org_id
        assert result.referee_user_id == referee_user_id
        assert result.referee_org_id is None
        assert result.status == STATUS_PENDING
        mock_session.add.assert_called_once_with(result)


class TestLinkRefereeOrg:
    """Tests for the link_referee_org service function."""

    async def test_no_referral_is_noop(self, mock_session: AsyncMock) -> None:
        """Test that a non-referred user's org creation does nothing."""
        with patch(
            f"{_REF}.get_referral_by_referee_user", AsyncMock(return_value=None)
        ):
            await link_referee_org(mock_session, uuid.uuid4(), uuid.uuid4())

        mock_session.add.assert_not_called()

    async def test_already_linked_is_noop(self, mock_session: AsyncMock) -> None:
        """Test that a referral already bound to an org is left untouched."""
        referral = Referral(
            referrer_org_id=uuid.uuid4(),
            referee_user_id=uuid.uuid4(),
            referee_org_id=uuid.uuid4(),
            status=STATUS_PENDING,
        )
        with patch(
            f"{_REF}.get_referral_by_referee_user", AsyncMock(return_value=referral)
        ):
            await link_referee_org(mock_session, referral.referee_user_id, uuid.uuid4())

        mock_session.add.assert_not_called()

    async def test_self_referral_is_noop(self, mock_session: AsyncMock) -> None:
        """Test that binding to the referrer's own org is rejected."""
        org_id = uuid.uuid4()
        referral = Referral(
            referrer_org_id=org_id,
            referee_user_id=uuid.uuid4(),
            status=STATUS_PENDING,
        )
        with patch(
            f"{_REF}.get_referral_by_referee_user", AsyncMock(return_value=referral)
        ):
            await link_referee_org(mock_session, referral.referee_user_id, org_id)

        assert referral.referee_org_id is None
        mock_session.add.assert_not_called()

    async def test_referrer_member_is_noop(self, mock_session: AsyncMock) -> None:
        """Test that a referee who already belongs to the referrer org is rejected."""
        referral = Referral(
            referrer_org_id=uuid.uuid4(),
            referee_user_id=uuid.uuid4(),
            status=STATUS_PENDING,
        )
        with (
            patch(
                f"{_REF}.get_referral_by_referee_user",
                AsyncMock(return_value=referral),
            ),
            patch(
                "ai_shop_helper_backend.services.org_users.get_org_user",
                AsyncMock(return_value=object()),
            ),
        ):
            await link_referee_org(mock_session, referral.referee_user_id, uuid.uuid4())

        assert referral.referee_org_id is None
        mock_session.add.assert_not_called()

    async def test_binds_first_org(self, mock_session: AsyncMock) -> None:
        """Test that a fresh referral is bound to the referee's first org."""
        org_id = uuid.uuid4()
        referral = Referral(
            referrer_org_id=uuid.uuid4(),
            referee_user_id=uuid.uuid4(),
            status=STATUS_PENDING,
        )
        with (
            patch(
                f"{_REF}.get_referral_by_referee_user",
                AsyncMock(return_value=referral),
            ),
            patch(
                "ai_shop_helper_backend.services.org_users.get_org_user",
                AsyncMock(return_value=None),
            ),
        ):
            await link_referee_org(mock_session, referral.referee_user_id, org_id)

        assert referral.referee_org_id == org_id
        mock_session.add.assert_called_once_with(referral)


class TestCountRewardedThisMonth:
    """Tests for the count_rewarded_this_month service function."""

    async def test_returns_count(self, mock_session: AsyncMock) -> None:
        """Test that the rewarded-this-month count is returned from the query."""
        mock_session.exec.return_value.one.return_value = 3

        result = await count_rewarded_this_month(mock_session, uuid.uuid4())

        assert result == 3


class TestOnOrgPaid:
    """Tests for the on_org_paid service function."""

    async def test_no_pending_referral_is_noop(self, mock_session: AsyncMock) -> None:
        """Test that a payment with no pending referral does nothing."""
        mock_session.exec.return_value.first.return_value = None

        result = await on_org_paid(mock_session, uuid.uuid4())

        assert result is None

    async def test_over_cap_marks_capped_without_grant(
        self, mock_session: AsyncMock
    ) -> None:
        """Test that a referral over the monthly cap is capped and grants nothing."""
        referral = Referral(
            referrer_org_id=uuid.uuid4(),
            referee_user_id=uuid.uuid4(),
            referee_org_id=uuid.uuid4(),
            status=STATUS_PENDING,
        )
        mock_session.exec.return_value.first.return_value = referral
        with (
            patch(
                f"{_REF}.count_rewarded_this_month",
                AsyncMock(return_value=REFERRAL_REWARD.monthly_cap),
            ),
            patch(
                "ai_shop_helper_backend.services.billing.grant_purchased",
                AsyncMock(),
            ) as grant,
        ):
            result = await on_org_paid(mock_session, referral.referee_org_id)

        assert result is referral
        assert referral.status == STATUS_CAPPED
        assert referral.qualified_at is not None
        assert referral.rewarded_at is None
        grant.assert_not_called()

    async def test_rewards_both_sides_within_cap(
        self, mock_session: AsyncMock, make_org: Callable[..., Org]
    ) -> None:
        """Test that a qualifying referral grants referrer and referee credits and is rewarded."""
        referrer_org = make_org()
        referee_org = make_org()
        referral = Referral(
            referrer_org_id=referrer_org.id,
            referee_user_id=uuid.uuid4(),
            referee_org_id=referee_org.id,
            status=STATUS_PENDING,
        )
        mock_session.exec.return_value.first.return_value = referral
        with (
            patch(f"{_REF}.count_rewarded_this_month", AsyncMock(return_value=0)),
            patch(
                f"{_REF}.get_org_by_id",
                AsyncMock(side_effect=[referrer_org, referee_org]),
            ),
            patch(
                "ai_shop_helper_backend.services.billing.grant_purchased",
                AsyncMock(),
            ) as grant,
        ):
            result = await on_org_paid(mock_session, referee_org.id)

        assert result is referral
        assert referral.status == STATUS_REWARDED
        assert referral.rewarded_at is not None
        assert referral.referrer_credits == REFERRAL_REWARD.referrer_credits
        assert referral.referee_credits == REFERRAL_REWARD.referee_credits
        assert grant.await_count == 2

    async def test_skips_referee_grant_when_zero(
        self, mock_session: AsyncMock, make_org: Callable[..., Org]
    ) -> None:
        """Test that a zero referee reward grants only the referrer."""
        referrer_org = make_org()
        referee_org = make_org()
        referral = Referral(
            referrer_org_id=referrer_org.id,
            referee_user_id=uuid.uuid4(),
            referee_org_id=referee_org.id,
            status=STATUS_PENDING,
        )
        mock_session.exec.return_value.first.return_value = referral
        with (
            patch(f"{_REF}.REFERRAL_REWARD", ReferralReward(500, 0, 10)),
            patch(f"{_REF}.count_rewarded_this_month", AsyncMock(return_value=0)),
            patch(f"{_REF}.get_org_by_id", AsyncMock(return_value=referrer_org)),
            patch(
                "ai_shop_helper_backend.services.billing.grant_purchased",
                AsyncMock(),
            ) as grant,
        ):
            result = await on_org_paid(mock_session, referee_org.id)

        assert result is referral
        assert referral.status == STATUS_REWARDED
        assert grant.await_count == 1
        assert referral.referee_credits == 0
