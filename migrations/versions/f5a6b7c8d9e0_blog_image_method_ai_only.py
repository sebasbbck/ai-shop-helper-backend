from collections.abc import Sequence

from alembic import op

revision: str = "f5a6b7c8d9e0"
down_revision: str | Sequence[str] | None = "e4f5a6b7c8d9"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        """
        UPDATE agentinput
        SET options = '["ai_images"]'
        WHERE key = 'image_method'
        """
    )


def downgrade() -> None:
    op.execute(
        """
        UPDATE agentinput
        SET options = '["ia_images", "stock", "upload"]'
        WHERE key = 'image_method'
        """
    )
