import uuid

import httpx
from fastapi import APIRouter, BackgroundTasks, Body, HTTPException

from ai_shop_helper_backend.core.config import settings
from ai_shop_helper_backend.core.utils import get_datetime_utc

router = APIRouter(prefix="/n8n-test", tags=["n8n-test"])

tasks: dict[str, dict] = {}


@router.post("/start")
async def start_workflow(
    background_tasks: BackgroundTasks,
    payload: dict = Body(...),
) -> dict:
    workflow_id = payload.get("workflow_id")
    data = payload.get("data", {})
    aws = payload.get("aws", True)
    n8n_url = payload.get("n8n_url", "")
    task_id = str(uuid.uuid4())
    tasks[task_id] = {
        "status": "pending",
        "workflow_id": workflow_id,
        "created_at": get_datetime_utc().isoformat(),
        "result": None,
    }
    background_tasks.add_task(_call_n8n, task_id, workflow_id, data, aws, n8n_url)
    return {"task_id": task_id}


@router.get("/tasks/{task_id}")
async def get_task(task_id: str) -> dict:
    if task_id not in tasks:
        raise HTTPException(404)
    return tasks[task_id]


@router.post("/n8n-callback")  # task_id in route?
async def n8n_callback(payload: dict = Body(...)) -> dict:
    task_id = payload.get("task_id")
    if not task_id or task_id not in tasks:
        raise HTTPException(404)

    if payload.get("success"):
        tasks[task_id]["status"] = "completed"
        tasks[task_id]["result"] = payload.get("data")
    else:
        tasks[task_id]["status"] = "failed"
        tasks[task_id]["error"] = payload.get("error")

    tasks[task_id]["completed_at"] = get_datetime_utc().isoformat()

    return {"status": "OK"}


async def _call_n8n(
    task_id: str, workflow_id: str, data: dict, aws: bool, n8n_url: str
) -> None:
    try:
        tasks[task_id]["status"] = "processing"
        callback_url = f"{settings.BACKEND_URL}/n8n-test/n8n-callback"

        if aws:
            n8n_url = f"{settings.N8N_URL}/webhook"

        webhook_url = f"{n8n_url}/{workflow_id}"

        async with httpx.AsyncClient(timeout=30.0) as client:
            await client.post(
                webhook_url,
                json={
                    "task_id": task_id,
                    "callback_url": callback_url,
                    "data": data,
                },
            )
    except Exception as e:
        tasks[task_id]["status"] = "failed"
        tasks[task_id]["error"] = str(e)
