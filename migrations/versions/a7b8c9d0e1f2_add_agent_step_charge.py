"""add agent step charge

Revision ID: a7b8c9d0e1f2
Revises: f1a2b3c4d5e6
Create Date: 2026-07-29 00:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
import sqlmodel
from alembic import op

revision: str = "a7b8c9d0e1f2"
down_revision: str | Sequence[str] | None = "f1a2b3c4d5e6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "agentstepcharge",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("step_id", sa.Uuid(), nullable=False),
        sa.Column("order", sa.Integer(), nullable=False),
        sa.Column("reason", sqlmodel.sql.sqltypes.AutoString(length=64), nullable=False),
        sa.Column("credits", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["step_id"], ["agentstep.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("step_id", "reason", name="uq_agentstepcharge_step_reason"),
    )
    op.create_index(
        op.f("ix_agentstepcharge_step_id"), "agentstepcharge", ["step_id"], unique=False
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_agentstepcharge_step_id"), table_name="agentstepcharge")
    op.drop_table("agentstepcharge")
