"""step connection_type and multi-connection per project

Revision ID: e29a470776e6
Revises: a6b7c8d9e0f1
Create Date: 2026-07-20

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "e29a470776e6"
down_revision: str | Sequence[str] | None = "a6b7c8d9e0f1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

connectiontype = postgresql.ENUM(name="connectiontype", create_type=False)


def upgrade() -> None:
    op.add_column(
        "agentstep",
        sa.Column("connection_type", connectiontype, nullable=True),
    )
    op.execute(
        "UPDATE agentstep SET connection_type = 'wordpress' "
        "WHERE slug = 'generate' AND runner_ref = 'blog_generate'"
    )

    op.drop_column("projecttype", "connection_type")

    op.drop_constraint("connection_project_id_key", "connection", type_="unique")
    op.create_unique_constraint(
        "uq_connection_project_type",
        "connection",
        ["project_id", "connection_type"],
    )


def downgrade() -> None:
    op.drop_constraint("uq_connection_project_type", "connection", type_="unique")
    op.create_unique_constraint(
        "connection_project_id_key", "connection", ["project_id"]
    )

    op.add_column(
        "projecttype",
        sa.Column("connection_type", connectiontype, nullable=True),
    )

    op.drop_column("agentstep", "connection_type")
