import httpx

from ai_shop_helper_backend.core.config import settings
from ai_shop_helper_backend.runners.base import StartResult, is_final_sync_result


class N8nRunner:
    def __init__(self, transport: httpx.AsyncBaseTransport | None = None) -> None:
        self._transport = transport

    async def start(
        self,
        *,
        runner_ref: str,
        inputs: dict,
        task_id: str,
        callback_url: str,
    ) -> StartResult:
        webhook_url = f"{settings.N8N_URL}/webhook/{runner_ref}"
        payload = {**inputs, "task_id": task_id, "callback_url": callback_url}

        client_kwargs: dict = {"timeout": 30}
        if self._transport is not None:
            client_kwargs["transport"] = self._transport

        try:
            async with httpx.AsyncClient(**client_kwargs) as client:
                response = await client.post(webhook_url, json=payload)
        except httpx.RequestError as exc:
            return StartResult(
                accepted=False,
                status_code=0,
                sync_output=None,
                external_ref=task_id,
                error=str(exc),
            )

        if response.is_success:
            try:
                body = response.json()
            except Exception:
                body = {}
            if not isinstance(body, dict):
                body = {}
            return StartResult(
                accepted=True,
                status_code=response.status_code,
                sync_output=body if is_final_sync_result(body) else None,
                external_ref=task_id,
                error=None,
            )

        try:
            error_text = response.text[:500]
        except Exception:
            error_text = "non-2xx response"

        return StartResult(
            accepted=False,
            status_code=response.status_code,
            sync_output=None,
            external_ref=task_id,
            error=error_text,
        )
