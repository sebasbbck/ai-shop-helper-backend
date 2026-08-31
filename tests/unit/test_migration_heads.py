"""The migration graph must resolve to a single head (no database required)."""

from alembic.config import Config
from alembic.script import ScriptDirectory


def test_single_alembic_head() -> None:
    """Exactly one head so ``alembic upgrade head`` is unambiguous.

    A migration that revises a non-tip revision creates a fork (multiple heads),
    which breaks the deploy migrate step.
    """
    cfg = Config()
    cfg.set_main_option("script_location", "migrations")
    heads = ScriptDirectory.from_config(cfg).get_heads()
    assert len(heads) == 1, f"Expected a single migration head, found {heads}"
