"""Add google to the connectiontype enum

Revision ID: 47cfa6311bb6
Revises: 3eedd5652a02
Create Date: 2026-07-20 00:00:01.000000
"""

from collections.abc import Sequence

from alembic import op

revision: str = "47cfa6311bb6"
down_revision: str | Sequence[str] | None = "3eedd5652a02"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("ALTER TYPE connectiontype ADD VALUE IF NOT EXISTS 'google'")


def downgrade() -> None:
    # Postgres does not support removing enum values; no-op.
    pass
