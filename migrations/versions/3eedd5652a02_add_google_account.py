"""Add google_account table (login identity link only, no tokens)

Revision ID: 3eedd5652a02
Revises: b8c9d0e1f2a3
Create Date: 2026-07-20 00:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "3eedd5652a02"
down_revision: str | Sequence[str] | None = "b8c9d0e1f2a3"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "googleaccount",
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("google_id", sa.String(), nullable=False),
        sa.Column("google_email", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["user.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("google_id", name="uq_googleaccount_google_id"),
        sa.UniqueConstraint("user_id", name="uq_googleaccount_user_id"),
    )
    op.create_index(
        "ix_googleaccount_google_id", "googleaccount", ["google_id"], unique=True
    )
    op.create_index(
        "ix_googleaccount_user_id", "googleaccount", ["user_id"], unique=True
    )


def downgrade() -> None:
    op.drop_index("ix_googleaccount_user_id", table_name="googleaccount")
    op.drop_index("ix_googleaccount_google_id", table_name="googleaccount")
    op.drop_table("googleaccount")
