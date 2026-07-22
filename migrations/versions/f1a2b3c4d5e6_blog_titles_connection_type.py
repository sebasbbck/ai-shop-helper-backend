"""blog_titles step connection_type wordpress

Revision ID: f1a2b3c4d5e6
Revises: e29a470776e6
Create Date: 2026-07-22

"""

from collections.abc import Sequence

from alembic import op

revision: str = "f1a2b3c4d5e6"
down_revision: str | Sequence[str] | None = "e29a470776e6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        "UPDATE agentstep SET connection_type = 'wordpress' "
        "WHERE slug = 'titles' AND runner_ref = 'blog_titles'"
    )


def downgrade() -> None:
    op.execute(
        "UPDATE agentstep SET connection_type = NULL "
        "WHERE slug = 'titles' AND runner_ref = 'blog_titles'"
    )
