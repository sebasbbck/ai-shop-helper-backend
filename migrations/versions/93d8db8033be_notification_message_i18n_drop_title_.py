"""Notification message i18n: drop title/body

Revision ID: 93d8db8033be
Revises: 23560ae6402b
Create Date: 2026-09-03 11:14:59.223669
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "93d8db8033be"
down_revision: str | Sequence[str] | None = "23560ae6402b"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_column("notification", "title")
    op.drop_column("notification", "body")


def downgrade() -> None:
    op.add_column(
        "notification", sa.Column("body", sa.String(), nullable=False, server_default="")
    )
    op.add_column(
        "notification",
        sa.Column("title", sa.String(length=255), nullable=False, server_default=""),
    )
