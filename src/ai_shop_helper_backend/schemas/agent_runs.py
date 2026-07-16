from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel

from ai_shop_helper_backend.models.agent_runs import InputScope, InputType, RunStatus


class AgentInputSchema(BaseModel):
    id: UUID
    key: str
    input_type: InputType
    options: list[Any] | None
    options_from_step_slug: str | None
    scope: InputScope
    order: int
    required: bool
    label_i18n_key: str

    model_config = {"from_attributes": True}


class AgentStepSchema(BaseModel):
    id: UUID
    order: int
    slug: str
    inputs: list[AgentInputSchema]

    model_config = {"from_attributes": True}


class AgentSchemaResponse(BaseModel):
    agent_id: UUID
    steps: list[AgentStepSchema]


class ProjectContextFieldSchema(BaseModel):
    key: str
    input_type: str
    required: bool
    label_i18n_key: str


class ProjectContextResponse(BaseModel):
    project_id: UUID
    fields: list[ProjectContextFieldSchema]
    values: dict[str, str]


class ProjectContextPut(BaseModel):
    values: dict[str, str]


class CreateRunBody(BaseModel):
    run_inputs: dict[str, str] = {}


class SubmitRunInputsBody(BaseModel):
    inputs: dict[str, str]


class AgentRunStepPublic(BaseModel):
    id: UUID
    step_id: UUID
    status: RunStatus
    input_snapshot: dict[str, Any]
    output: dict[str, Any] | None
    external_ref: str | None
    started_at: datetime | None
    finished_at: datetime | None
    error: str | None

    model_config = {"from_attributes": True}


class AgentRunPublic(BaseModel):
    id: UUID
    project_id: UUID
    agent_id: UUID
    status: RunStatus
    current_step_order: int
    error: str | None
    credits_debited: int
    created_by: UUID
    created_at: datetime
    finished_at: datetime | None
    steps: list[AgentRunStepPublic]

    model_config = {"from_attributes": True}


class CallbackBody(BaseModel):
    success: bool
    data: dict[str, Any] | None = None
    error: str | None = None


class CallbackResponse(BaseModel):
    status: str
