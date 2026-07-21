"""add billing tables

Revision ID: a1b2c3d4e5f6
Revises: c7d1e9f2a3b4
Create Date: 2026-07-06 08:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
import sqlmodel
from alembic import op

revision: str = "a1b2c3d4e5f6"
down_revision: str | Sequence[str] | None = "c7d1e9f2a3b4"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_column("org", "credits")
    op.add_column(
        "org",
        sa.Column(
            "subscription_credits",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
    )
    op.add_column(
        "org",
        sa.Column(
            "purchased_credits",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
    )

    op.create_table(
        "credittransaction",
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("org_id", sa.Uuid(), nullable=False),
        sa.Column("amount", sa.Integer(), nullable=False),
        sa.Column(
            "bucket", sqlmodel.sql.sqltypes.AutoString(length=64), nullable=False
        ),
        sa.Column("balance_after", sa.Integer(), nullable=False),
        sa.Column(
            "reason", sqlmodel.sql.sqltypes.AutoString(length=64), nullable=False
        ),
        sa.Column(
            "stripe_event_id",
            sqlmodel.sql.sqltypes.AutoString(length=255),
            nullable=True,
        ),
        sa.Column(
            "metadata_json",
            sqlmodel.sql.sqltypes.AutoString(length=4096),
            nullable=True,
        ),
        sa.ForeignKeyConstraint(["org_id"], ["org.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("stripe_event_id"),
    )
    op.create_index(
        op.f("ix_credittransaction_org_id"),
        "credittransaction",
        ["org_id"],
        unique=False,
    )

    op.create_table(
        "stripecustomer",
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("org_id", sa.Uuid(), nullable=False),
        sa.Column(
            "stripe_customer_id",
            sqlmodel.sql.sqltypes.AutoString(length=255),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["org_id"], ["org.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("org_id"),
        sa.UniqueConstraint("stripe_customer_id"),
    )
    op.create_index(
        op.f("ix_stripecustomer_org_id"),
        "stripecustomer",
        ["org_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_stripecustomer_stripe_customer_id"),
        "stripecustomer",
        ["stripe_customer_id"],
        unique=True,
    )

    op.create_table(
        "stripeprocessedevent",
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "stripe_event_id",
            sqlmodel.sql.sqltypes.AutoString(length=255),
            nullable=False,
        ),
        sa.Column("type", sqlmodel.sql.sqltypes.AutoString(length=255), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("stripe_event_id"),
    )
    op.create_index(
        op.f("ix_stripeprocessedevent_stripe_event_id"),
        "stripeprocessedevent",
        ["stripe_event_id"],
        unique=True,
    )

    op.create_table(
        "stripesubscription",
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("org_id", sa.Uuid(), nullable=False),
        sa.Column(
            "stripe_subscription_id",
            sqlmodel.sql.sqltypes.AutoString(length=255),
            nullable=False,
        ),
        sa.Column(
            "price_id", sqlmodel.sql.sqltypes.AutoString(length=255), nullable=False
        ),
        sa.Column("plan", sqlmodel.sql.sqltypes.AutoString(length=64), nullable=False),
        sa.Column(
            "status", sqlmodel.sql.sqltypes.AutoString(length=64), nullable=False
        ),
        sa.Column("credits_per_cycle", sa.Integer(), nullable=False),
        sa.Column("current_period_end", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["org_id"], ["org.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("stripe_subscription_id"),
    )
    op.create_index(
        op.f("ix_stripesubscription_org_id"),
        "stripesubscription",
        ["org_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_stripesubscription_stripe_subscription_id"),
        "stripesubscription",
        ["stripe_subscription_id"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_stripesubscription_stripe_subscription_id"),
        table_name="stripesubscription",
    )
    op.drop_index(op.f("ix_stripesubscription_org_id"), table_name="stripesubscription")
    op.drop_table("stripesubscription")

    op.drop_index(
        op.f("ix_stripeprocessedevent_stripe_event_id"),
        table_name="stripeprocessedevent",
    )
    op.drop_table("stripeprocessedevent")

    op.drop_index(
        op.f("ix_stripecustomer_stripe_customer_id"), table_name="stripecustomer"
    )
    op.drop_index(op.f("ix_stripecustomer_org_id"), table_name="stripecustomer")
    op.drop_table("stripecustomer")

    op.drop_index(op.f("ix_credittransaction_org_id"), table_name="credittransaction")
    op.drop_table("credittransaction")

    op.drop_column("org", "purchased_credits")
    op.drop_column("org", "subscription_credits")
    op.add_column(
        "org",
        sa.Column("credits", sa.Integer(), nullable=False, server_default="0"),
    )
