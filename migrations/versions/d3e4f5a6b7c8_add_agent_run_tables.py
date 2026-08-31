"""add agent run tables

Revision ID: d3e4f5a6b7c8
Revises: b2c3d4e5f6a7
Create Date: 2026-07-14 09:00:00.000000
"""

from typing import Sequence

import sqlalchemy as sa
import sqlmodel
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "d3e4f5a6b7c8"
down_revision: str | Sequence[str] | None = "b2c3d4e5f6a7"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

runnertype = postgresql.ENUM("n8n", name="runnertype", create_type=False)
inputtype = postgresql.ENUM(
    "text", "textarea", "select", name="inputtype", create_type=False
)
inputscope = postgresql.ENUM("project", "run", name="inputscope", create_type=False)
runstatus = postgresql.ENUM(
    "pending",
    "running",
    "awaiting_input",
    "success",
    "failed",
    name="runstatus",
    create_type=False,
)


def upgrade() -> None:
    bind = op.get_bind()
    runnertype.create(bind, checkfirst=True)
    inputtype.create(bind, checkfirst=True)
    inputscope.create(bind, checkfirst=True)
    runstatus.create(bind, checkfirst=True)

    op.create_table(
        "agentstep",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("agent_id", sa.Uuid(), nullable=False),
        sa.Column("order", sa.Integer(), nullable=False),
        sa.Column("slug", sqlmodel.sql.sqltypes.AutoString(length=128), nullable=False),
        sa.Column(
            "runner_type",
            runnertype,
            nullable=False,
        ),
        sa.Column("runner_ref", sqlmodel.sql.sqltypes.AutoString(length=255), nullable=False),
        sa.Column("token_cost", sa.Integer(), nullable=False, server_default="0"),
        sa.ForeignKeyConstraint(["agent_id"], ["agent.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("agent_id", "order", name="uq_agentstep_agent_order"),
        sa.UniqueConstraint("agent_id", "slug", name="uq_agentstep_agent_slug"),
    )
    op.create_index(
        op.f("ix_agentstep_agent_id"),
        "agentstep",
        ["agent_id"],
        unique=False,
    )

    op.create_table(
        "agentinput",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("agent_id", sa.Uuid(), nullable=False),
        sa.Column("step_id", sa.Uuid(), nullable=True),
        sa.Column("key", sqlmodel.sql.sqltypes.AutoString(length=128), nullable=False),
        sa.Column(
            "input_type",
            inputtype,
            nullable=False,
        ),
        sa.Column("options", sa.JSON(), nullable=True),
        sa.Column(
            "options_from_step_slug",
            sqlmodel.sql.sqltypes.AutoString(length=128),
            nullable=True,
        ),
        sa.Column(
            "scope",
            inputscope,
            nullable=False,
        ),
        sa.Column("order", sa.Integer(), nullable=False),
        sa.Column("required", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column(
            "label_i18n_key",
            sqlmodel.sql.sqltypes.AutoString(length=255),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["agent_id"], ["agent.id"]),
        sa.ForeignKeyConstraint(["step_id"], ["agentstep.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_agentinput_agent_id"),
        "agentinput",
        ["agent_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_agentinput_step_id"),
        "agentinput",
        ["step_id"],
        unique=False,
    )

    op.create_table(
        "projectagentinput",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("input_key", sqlmodel.sql.sqltypes.AutoString(length=128), nullable=False),
        sa.Column("value", sqlmodel.sql.sqltypes.AutoString(length=4096), nullable=False),
        sa.ForeignKeyConstraint(["project_id"], ["project.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "project_id", "input_key", name="uq_projectagentinput_project_key"
        ),
    )
    op.create_index(
        op.f("ix_projectagentinput_project_id"),
        "projectagentinput",
        ["project_id"],
        unique=False,
    )

    op.create_table(
        "agentrun",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("agent_id", sa.Uuid(), nullable=False),
        sa.Column(
            "status",
            runstatus,
            nullable=False,
            server_default="pending",
        ),
        sa.Column("current_step_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "error",
            sqlmodel.sql.sqltypes.AutoString(length=2048),
            nullable=True,
        ),
        sa.Column("credits_debited", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("debited_sub", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("debited_purchased", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_by", sa.Uuid(), nullable=False),
        sa.Column("finished_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["agent_id"], ["agent.id"]),
        sa.ForeignKeyConstraint(["created_by"], ["user.id"]),
        sa.ForeignKeyConstraint(["project_id"], ["project.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_agentrun_agent_id"),
        "agentrun",
        ["agent_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_agentrun_project_id"),
        "agentrun",
        ["project_id"],
        unique=False,
    )

    op.create_table(
        "agentrunstep",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("run_id", sa.Uuid(), nullable=False),
        sa.Column("step_id", sa.Uuid(), nullable=False),
        sa.Column(
            "status",
            runstatus,
            nullable=False,
        ),
        sa.Column("input_snapshot", sa.JSON(), nullable=False),
        sa.Column("output", sa.JSON(), nullable=True),
        sa.Column(
            "external_ref",
            sqlmodel.sql.sqltypes.AutoString(length=255),
            nullable=True,
        ),
        sa.Column("started_at", sa.DateTime(), nullable=True),
        sa.Column("finished_at", sa.DateTime(), nullable=True),
        sa.Column(
            "error",
            sqlmodel.sql.sqltypes.AutoString(length=2048),
            nullable=True,
        ),
        sa.ForeignKeyConstraint(["run_id"], ["agentrun.id"]),
        sa.ForeignKeyConstraint(["step_id"], ["agentstep.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_agentrunstep_run_id"),
        "agentrunstep",
        ["run_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_agentrunstep_step_id"),
        "agentrunstep",
        ["step_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_agentrunstep_step_id"), table_name="agentrunstep")
    op.drop_index(op.f("ix_agentrunstep_run_id"), table_name="agentrunstep")
    op.drop_table("agentrunstep")

    op.drop_index(op.f("ix_agentrun_project_id"), table_name="agentrun")
    op.drop_index(op.f("ix_agentrun_agent_id"), table_name="agentrun")
    op.drop_table("agentrun")

    op.drop_index(
        op.f("ix_projectagentinput_project_id"), table_name="projectagentinput"
    )
    op.drop_table("projectagentinput")

    op.drop_index(op.f("ix_agentinput_step_id"), table_name="agentinput")
    op.drop_index(op.f("ix_agentinput_agent_id"), table_name="agentinput")
    op.drop_table("agentinput")

    op.drop_index(op.f("ix_agentstep_agent_id"), table_name="agentstep")
    op.drop_table("agentstep")

    op.execute("DROP TYPE IF EXISTS runstatus")
    op.execute("DROP TYPE IF EXISTS inputscope")
    op.execute("DROP TYPE IF EXISTS inputtype")
    op.execute("DROP TYPE IF EXISTS runnertype")
