from typing import Protocol

from pydantic import BaseModel


class StartResult(BaseModel):
    accepted: bool
    status_code: int
    sync_output: dict | None
    external_ref: str | None
    error: str | None


def is_final_sync_result(body: dict) -> bool:
    if "data" in body:
        return True
    for key in ("context_titles", "title", "url_post"):
        if key in body:
            return True
    return False


class AgentRunner(Protocol):
    async def start(
        self,
        *,
        runner_ref: str,
        inputs: dict,
        task_id: str,
        callback_url: str,
    ) -> StartResult: ...
