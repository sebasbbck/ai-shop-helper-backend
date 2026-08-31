"""add email tables

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2026-07-10 08:00:00.000000
"""

from typing import Sequence

import sqlalchemy as sa
import sqlmodel
from alembic import op

revision: str = "b2c3d4e5f6a7"
down_revision: str | Sequence[str] | None = "a1b2c3d4e5f6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "user",
        sa.Column(
            "email_verified",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )
    op.execute('UPDATE "user" SET email_verified = true')

    op.create_table(
        "authemailtoken",
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("token", sqlmodel.sql.sqltypes.AutoString(length=255), nullable=False),
        sa.Column("purpose", sqlmodel.sql.sqltypes.AutoString(length=32), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column("used_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["user.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("token"),
    )
    op.create_index(
        op.f("ix_authemailtoken_user_id"),
        "authemailtoken",
        ["user_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_authemailtoken_token"),
        "authemailtoken",
        ["token"],
        unique=True,
    )

    op.create_table(
        "emailoutbox",
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("to_email", sqlmodel.sql.sqltypes.AutoString(length=255), nullable=False),
        sa.Column("first_name", sqlmodel.sql.sqltypes.AutoString(length=255), nullable=True),
        sa.Column("email_type", sqlmodel.sql.sqltypes.AutoString(length=64), nullable=False),
        sa.Column("locale", sqlmodel.sql.sqltypes.AutoString(length=16), nullable=False),
        sa.Column("data_json", sqlmodel.sql.sqltypes.AutoString(length=8192), nullable=False),
        sa.Column(
            "external_id",
            sqlmodel.sql.sqltypes.AutoString(length=255),
            nullable=False,
        ),
        sa.Column(
            "status",
            sqlmodel.sql.sqltypes.AutoString(length=16),
            nullable=False,
            server_default="pending",
        ),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("next_attempt_at", sa.DateTime(), nullable=False),
        sa.Column(
            "last_error",
            sqlmodel.sql.sqltypes.AutoString(length=2048),
            nullable=True,
        ),
        sa.Column("sent_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("external_id"),
    )
    op.create_index(
        op.f("ix_emailoutbox_to_email"),
        "emailoutbox",
        ["to_email"],
        unique=False,
    )
    op.create_index(
        op.f("ix_emailoutbox_status"),
        "emailoutbox",
        ["status"],
        unique=False,
    )
    op.create_index(
        op.f("ix_emailoutbox_next_attempt_at"),
        "emailoutbox",
        ["next_attempt_at"],
        unique=False,
    )
    op.create_index(
        op.f("ix_emailoutbox_external_id"),
        "emailoutbox",
        ["external_id"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_emailoutbox_external_id"), table_name="emailoutbox")
    op.drop_index(op.f("ix_emailoutbox_next_attempt_at"), table_name="emailoutbox")
    op.drop_index(op.f("ix_emailoutbox_status"), table_name="emailoutbox")
    op.drop_index(op.f("ix_emailoutbox_to_email"), table_name="emailoutbox")
    op.drop_table("emailoutbox")

    op.drop_index(op.f("ix_authemailtoken_token"), table_name="authemailtoken")
    op.drop_index(op.f("ix_authemailtoken_user_id"), table_name="authemailtoken")
    op.drop_table("authemailtoken")

    op.drop_column("user", "email_verified")
