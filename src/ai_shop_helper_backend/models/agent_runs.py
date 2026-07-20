import enum
import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import JSON, Column, UniqueConstraint
from sqlalchemy import Enum as SAEnum
from sqlmodel import Field, SQLModel

from ai_shop_helper_backend.models.mixins import CreatedAtMixin, UUIDMixin


class RunnerType(enum.StrEnum):
    n8n = "n8n"


class InputType(enum.StrEnum):
    text = "text"
    textarea = "textarea"
    select = "select"


class InputScope(enum.StrEnum):
    project = "project"
    run = "run"


class RunStatus(enum.StrEnum):
    pending = "pending"
    running = "running"
    awaiting_input = "awaiting_input"
    success = "success"
    failed = "failed"


class AgentStep(UUIDMixin, SQLModel, table=True):
    __tablename__ = "agentstep"
    __table_args__ = (
        UniqueConstraint("agent_id", "order", name="uq_agentstep_agent_order"),
        UniqueConstraint("agent_id", "slug", name="uq_agentstep_agent_slug"),
    )

    agent_id: uuid.UUID = Field(foreign_key="agent.id", index=True)
    order: int
    slug: str = Field(max_length=128)
    runner_type: RunnerType = Field(
        sa_column=Column(SAEnum(RunnerType, name="runnertype"), nullable=False)
    )
    runner_ref: str = Field(max_length=255)
    token_cost: int = Field(default=0)


class AgentInput(UUIDMixin, SQLModel, table=True):
    __tablename__ = "agentinput"

    agent_id: uuid.UUID = Field(foreign_key="agent.id", index=True)
    step_id: uuid.UUID | None = Field(
        default=None, foreign_key="agentstep.id", index=True
    )
    key: str = Field(max_length=128)
    input_type: InputType = Field(
        sa_column=Column(SAEnum(InputType, name="inputtype"), nullable=False)
    )
    options: list[Any] | None = Field(
        default=None, sa_column=Column(JSON, nullable=True)
    )
    options_from_step_slug: str | None = Field(default=None, max_length=128)
    scope: InputScope = Field(
        sa_column=Column(SAEnum(InputScope, name="inputscope"), nullable=False)
    )
    order: int
    required: bool = Field(default=True)
    label_i18n_key: str = Field(max_length=255)


class ProjectAgentInput(UUIDMixin, SQLModel, table=True):
    __tablename__ = "projectagentinput"
    __table_args__ = (
        UniqueConstraint(
            "project_id", "input_key", name="uq_projectagentinput_project_key"
        ),
    )

    project_id: uuid.UUID = Field(foreign_key="project.id", index=True)
    input_key: str = Field(max_length=128)
    value: str = Field(max_length=4096)


class AgentRun(UUIDMixin, CreatedAtMixin, SQLModel, table=True):
    __tablename__ = "agentrun"

    project_id: uuid.UUID = Field(foreign_key="project.id", index=True)
    agent_id: uuid.UUID = Field(foreign_key="agent.id", index=True)
    status: RunStatus = Field(
        default=RunStatus.pending,
        sa_column=Column(
            SAEnum(RunStatus, name="runstatus"),
            nullable=False,
            server_default="pending",
        ),
    )
    current_step_order: int = Field(default=0)
    error: str | None = Field(default=None, max_length=2048)
    credits_debited: int = Field(default=0)
    debited_sub: int = Field(default=0)
    debited_purchased: int = Field(default=0)
    created_by: uuid.UUID = Field(foreign_key="user.id")
    finished_at: datetime | None = Field(default=None)


class AgentRunStep(UUIDMixin, SQLModel, table=True):
    __tablename__ = "agentrunstep"

    run_id: uuid.UUID = Field(foreign_key="agentrun.id", index=True)
    step_id: uuid.UUID = Field(foreign_key="agentstep.id", index=True)
    status: RunStatus = Field(
        sa_column=Column(SAEnum(RunStatus, name="runstatus"), nullable=False)
    )
    input_snapshot: dict[str, Any] = Field(sa_column=Column(JSON, nullable=False))
    output: dict[str, Any] | None = Field(
        default=None, sa_column=Column(JSON, nullable=True)
    )
    external_ref: str | None = Field(default=None, max_length=255)
    started_at: datetime | None = Field(default=None)
    finished_at: datetime | None = Field(default=None)
    error: str | None = Field(default=None, max_length=2048)
