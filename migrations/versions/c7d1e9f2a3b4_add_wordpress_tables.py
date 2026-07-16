"""add wordpress tables

Revision ID: c7d1e9f2a3b4
Revises: 60ef5c669a21
Create Date: 2026-06-29 07:30:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
import sqlmodel
from alembic import op

revision: str = "c7d1e9f2a3b4"
down_revision: str | Sequence[str] | None = "60ef5c669a21"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "wordpressconnection",
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column(
            "site_url", sqlmodel.sql.sqltypes.AutoString(length=2048), nullable=False
        ),
        sa.Column(
            "username", sqlmodel.sql.sqltypes.AutoString(length=255), nullable=False
        ),
        sa.Column(
            "password_enc",
            sqlmodel.sql.sqltypes.AutoString(length=2048),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["project_id"], ["project.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("project_id"),
    )
    op.create_index(
        op.f("ix_wordpressconnection_project_id"),
        "wordpressconnection",
        ["project_id"],
        unique=False,
    )

    op.create_table(
        "wordpresstoken",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "token", sqlmodel.sql.sqltypes.AutoString(length=128), nullable=False
        ),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["project_id"], ["project.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_wordpresstoken_project_id"),
        "wordpresstoken",
        ["project_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_wordpresstoken_token"),
        "wordpresstoken",
        ["token"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_wordpresstoken_token"), table_name="wordpresstoken")
    op.drop_index(op.f("ix_wordpresstoken_project_id"), table_name="wordpresstoken")
    op.drop_table("wordpresstoken")
    op.drop_index(
        op.f("ix_wordpressconnection_project_id"), table_name="wordpressconnection"
    )
    op.drop_table("wordpressconnection")
