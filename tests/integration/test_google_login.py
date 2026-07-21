"""Integration tests for the /google login router."""

from collections.abc import Callable, Coroutine
from unittest.mock import AsyncMock, patch

from httpx import AsyncClient
from sqlmodel.ext.asyncio.session import AsyncSession

from ai_shop_helper_backend.core.config import settings
from ai_shop_helper_backend.models.users import User

_GOOGLE_TOKEN_RESPONSE = {"access_token": "google-access-token"}


def _userinfo(
    sub: str = "google-sub-1",
    email: str = "newuser@example.com",
    email_verified: bool = True,
    name: str = "New User",
) -> dict:
    return {"sub": sub, "email": email, "email_verified": email_verified, "name": name}


class TestLoginWithGoogle:
    async def test_returns_auth_url_and_sets_state_cookie(
        self, client: AsyncClient
    ) -> None:
        response = await client.get("/google/login")

        assert response.status_code == 200
        assert "accounts.google.com" in response.json()["auth_url"]
        assert "oauth_login_state" in response.cookies


class TestGoogleCallback:
    async def _start_login(self, client: AsyncClient) -> str:
        login_resp = await client.get("/google/login")
        state = login_resp.cookies["oauth_login_state"]
        client.cookies.set("oauth_login_state", state)
        return state

    async def test_invalid_state_redirects_to_error(self, client: AsyncClient) -> None:
        response = await client.get(
            "/google/callback",
            params={"code": "irrelevant", "state": "not-the-real-state"},
        )

        assert response.status_code in (302, 307)
        assert response.headers["location"].startswith(settings.GOOGLE_LOGIN_ERROR_URL)

    async def test_unverified_email_redirects_to_error(
        self, client: AsyncClient
    ) -> None:
        state = await self._start_login(client)

        with (
            patch(
                "ai_shop_helper_backend.routers.google.google_svc.exchange_code",
                new_callable=AsyncMock,
                return_value=_GOOGLE_TOKEN_RESPONSE,
            ),
            patch(
                "ai_shop_helper_backend.routers.google.google_svc.get_userinfo",
                new_callable=AsyncMock,
                return_value=_userinfo(email_verified=False),
            ),
        ):
            response = await client.get(
                "/google/callback", params={"code": "abc", "state": state}
            )

        assert response.status_code in (302, 307)
        assert "email_not_verified" in response.headers["location"]

    async def test_new_user_is_created_and_redirected_with_session(
        self, client: AsyncClient, session: AsyncSession
    ) -> None:
        state = await self._start_login(client)

        with (
            patch(
                "ai_shop_helper_backend.routers.google.google_svc.exchange_code",
                new_callable=AsyncMock,
                return_value=_GOOGLE_TOKEN_RESPONSE,
            ),
            patch(
                "ai_shop_helper_backend.routers.google.google_svc.get_userinfo",
                new_callable=AsyncMock,
                return_value=_userinfo(),
            ),
        ):
            response = await client.get(
                "/google/callback", params={"code": "abc", "state": state}
            )

        assert response.status_code in (302, 307)
        assert response.headers["location"] == settings.GOOGLE_LOGIN_SUCCESS_URL
        assert settings.REFRESH_TOKEN_COOKIE in response.cookies

        from sqlmodel import select

        from ai_shop_helper_backend.models.users import User as UserModel

        result = await session.exec(
            select(UserModel).where(UserModel.email == "newuser@example.com")
        )
        user = result.first()
        assert user is not None
        assert user.email_verified is True

    async def test_links_existing_unverified_user_by_email(
        self,
        client: AsyncClient,
        session: AsyncSession,
        create_user: Callable[..., Coroutine[None, None, User]],
    ) -> None:
        existing = await create_user(email="already@example.com", email_verified=False)
        state = await self._start_login(client)

        with (
            patch(
                "ai_shop_helper_backend.routers.google.google_svc.exchange_code",
                new_callable=AsyncMock,
                return_value=_GOOGLE_TOKEN_RESPONSE,
            ),
            patch(
                "ai_shop_helper_backend.routers.google.google_svc.get_userinfo",
                new_callable=AsyncMock,
                return_value=_userinfo(email=existing.email),
            ),
        ):
            response = await client.get(
                "/google/callback", params={"code": "abc", "state": state}
            )

        assert response.headers["location"] == settings.GOOGLE_LOGIN_SUCCESS_URL
        await session.refresh(existing)
        assert existing.email_verified is True
