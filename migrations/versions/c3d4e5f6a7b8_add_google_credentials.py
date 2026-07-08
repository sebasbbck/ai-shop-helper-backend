"""Add google_credentials table

Revision ID: c3d4e5f6a7b8
Revises: 60ef5c669a21
Create Date: 2026-07-07 00:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "c3d4e5f6a7b8"
down_revision: str | Sequence[str] | None = "60ef5c669a21"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "googlecredential",
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("google_id", sa.String(), nullable=False),
        sa.Column("google_email", sa.String(), nullable=False),
        sa.Column("access_token", sa.String(), nullable=False),
        sa.Column("refresh_token", sa.String(), nullable=False),
        sa.Column("token_expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("scopes", sa.String(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["user.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("google_id", name="uq_googlecredential_google_id"),
        sa.UniqueConstraint("user_id", name="uq_googlecredential_user_id"),
    )
    op.create_index(
        "ix_googlecredential_google_id", "googlecredential", ["google_id"], unique=True
    )
    op.create_index(
        "ix_googlecredential_user_id", "googlecredential", ["user_id"], unique=True
    )


def downgrade() -> None:
    op.drop_index("ix_googlecredential_user_id", table_name="googlecredential")
    op.drop_index("ix_googlecredential_google_id", table_name="googlecredential")
    op.drop_table("googlecredential")
