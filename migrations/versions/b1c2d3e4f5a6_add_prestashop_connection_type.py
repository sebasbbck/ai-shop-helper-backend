"""Add prestashop to the connectiontype enum

Revision ID: b1c2d3e4f5a6
Revises: 93d8db8033be
Create Date: 2026-09-14 00:00:01.000000
"""

from collections.abc import Sequence

from alembic import op

revision: str = "b1c2d3e4f5a6"
down_revision: str | Sequence[str] | None = "93d8db8033be"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("ALTER TYPE connectiontype ADD VALUE IF NOT EXISTS 'prestashop'")


def downgrade() -> None:
    # Postgres does not support removing enum values; no-op.
    pass
