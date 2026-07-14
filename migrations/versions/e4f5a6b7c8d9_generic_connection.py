from typing import Sequence

import sqlalchemy as sa
import sqlmodel
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "e4f5a6b7c8d9"
down_revision: str | Sequence[str] | None = "d3e4f5a6b7c8"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

connectiontype = postgresql.ENUM("wordpress", name="connectiontype", create_type=False)


def upgrade() -> None:
    op.drop_index("ix_wordpressconnection_project_id", table_name="wordpressconnection")
    op.drop_table("wordpressconnection")

    connectiontype.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "connection",
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("connection_type", connectiontype, nullable=False),
        sa.Column(
            "secrets_encrypted",
            sqlmodel.sql.sqltypes.AutoString(length=8192),
            nullable=False,
        ),
        sa.Column("created_by", sa.Uuid(), nullable=True),
        sa.ForeignKeyConstraint(["created_by"], ["user.id"]),
        sa.ForeignKeyConstraint(["project_id"], ["project.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("project_id"),
    )
    op.create_index(
        op.f("ix_connection_project_id"),
        "connection",
        ["project_id"],
        unique=False,
    )

    op.add_column(
        "projecttype",
        sa.Column("connection_type", connectiontype, nullable=True),
    )


def downgrade() -> None:
    op.drop_column("projecttype", "connection_type")

    op.drop_index(op.f("ix_connection_project_id"), table_name="connection")
    op.drop_table("connection")

    connectiontype.drop(op.get_bind(), checkfirst=True)

    op.create_table(
        "wordpressconnection",
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column(
            "site_url",
            sqlmodel.sql.sqltypes.AutoString(length=2048),
            nullable=False,
        ),
        sa.Column(
            "username",
            sqlmodel.sql.sqltypes.AutoString(length=255),
            nullable=False,
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
