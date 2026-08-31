"""add referral tables

Revision ID: b8c9d0e1f2a3
Revises: a7b8c9d0e1f2
Create Date: 2026-08-27 12:00:00.000000
"""

from typing import Sequence

import sqlalchemy as sa
import sqlmodel
from alembic import op

revision: str = "b8c9d0e1f2a3"
down_revision: str | Sequence[str] | None = "a7b8c9d0e1f2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "referralcode",
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("org_id", sa.Uuid(), nullable=False),
        sa.Column("code", sqlmodel.sql.sqltypes.AutoString(length=16), nullable=False),
        sa.Column("created_by", sa.Uuid(), nullable=True),
        sa.ForeignKeyConstraint(["org_id"], ["org.id"]),
        sa.ForeignKeyConstraint(["created_by"], ["user.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("org_id", name="uq_referralcode_org"),
        sa.UniqueConstraint("code"),
    )
    op.create_index(
        op.f("ix_referralcode_org_id"), "referralcode", ["org_id"], unique=False
    )
    op.create_index(
        op.f("ix_referralcode_code"), "referralcode", ["code"], unique=True
    )

    op.create_table(
        "referral",
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("referrer_org_id", sa.Uuid(), nullable=False),
        sa.Column("referee_user_id", sa.Uuid(), nullable=False),
        sa.Column("referee_org_id", sa.Uuid(), nullable=True),
        sa.Column("status", sqlmodel.sql.sqltypes.AutoString(length=32), nullable=False),
        sa.Column("qualified_at", sa.DateTime(), nullable=True),
        sa.Column("rewarded_at", sa.DateTime(), nullable=True),
        sa.Column("referrer_credits", sa.Integer(), nullable=True),
        sa.Column("referee_credits", sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(["referrer_org_id"], ["org.id"]),
        sa.ForeignKeyConstraint(["referee_user_id"], ["user.id"]),
        sa.ForeignKeyConstraint(["referee_org_id"], ["org.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("referee_user_id", name="uq_referral_referee_user"),
    )
    op.create_index(
        op.f("ix_referral_referrer_org_id"),
        "referral",
        ["referrer_org_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_referral_referee_user_id"),
        "referral",
        ["referee_user_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_referral_referee_org_id"),
        "referral",
        ["referee_org_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_referral_referee_org_id"), table_name="referral")
    op.drop_index(op.f("ix_referral_referee_user_id"), table_name="referral")
    op.drop_index(op.f("ix_referral_referrer_org_id"), table_name="referral")
    op.drop_table("referral")

    op.drop_index(op.f("ix_referralcode_code"), table_name="referralcode")
    op.drop_index(op.f("ix_referralcode_org_id"), table_name="referralcode")
    op.drop_table("referralcode")
