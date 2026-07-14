from typing import Protocol

import httpx

from ai_shop_helper_backend.core.config import settings
from ai_shop_helper_backend.core.email_types import notifuse_language


class EmailDeliveryError(Exception):
    """Raised when the email provider returns a non-2xx response or a request error."""


class EmailProvider(Protocol):
    async def send(
        self,
        *,
        to_email: str,
        first_name: str,
        locale: str,
        template_slug: str,
        data: dict,
        external_id: str,
    ) -> None: ...


class NotifuseProvider:
    """Sends transactional emails via the Notifuse /api/transactional.send endpoint."""

    def __init__(self, transport: httpx.AsyncBaseTransport | None = None) -> None:
        self._transport = transport

    async def send(
        self,
        *,
        to_email: str,
        first_name: str,
        locale: str,
        template_slug: str,
        data: dict,
        external_id: str,
    ) -> None:
        resolved_name = first_name or to_email.split("@")[0]
        payload = {
            "workspace_id": settings.NOTIFUSE_WORKSPACE_ID,
            "notification": {
                "id": template_slug,
                "external_id": external_id,
                "channels": ["email"],
                "contact": {
                    "email": to_email,
                    "language": notifuse_language(locale),
                    "first_name": resolved_name,
                },
                "data": data,
            },
        }
        url = f"{settings.NOTIFUSE_BASE_URL}/api/transactional.send"
        client_kwargs: dict = {"timeout": 30}
        if self._transport is not None:
            client_kwargs["transport"] = self._transport

        try:
            async with httpx.AsyncClient(**client_kwargs) as client:
                response = await client.post(
                    url,
                    json=payload,
                    headers={"Authorization": f"Bearer {settings.NOTIFUSE_API_KEY}"},
                )
        except httpx.RequestError as exc:
            raise EmailDeliveryError(f"Request error sending email: {exc}") from exc

        if not response.is_success:
            truncated = response.text[:500]
            raise EmailDeliveryError(
                f"Notifuse returned {response.status_code}: {truncated}"
            )


notifuse_provider = NotifuseProvider()
