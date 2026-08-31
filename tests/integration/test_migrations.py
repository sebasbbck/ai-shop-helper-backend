"""Migrations must apply cleanly on a real PostgreSQL from base to head.

The rest of the suite builds the schema with ``SQLModel.metadata.create_all`` and never
exercises Alembic, so bad DDL stays invisible until the deploy job runs
``alembic upgrade head`` against a real database. This test closes that gap. The
single-head check lives in ``tests/unit/test_migration_heads.py`` (no database needed).
"""

from urllib.parse import urlparse

import anyio
import pytest
from alembic import command
from alembic.config import Config
from testcontainers.postgres import PostgresContainer

from ai_shop_helper_backend.core.config import settings


async def test_migrations_upgrade_from_scratch(monkeypatch: pytest.MonkeyPatch) -> None:
    """Every migration applies cleanly on an empty PostgreSQL from base to head.

    Catches broken DDL (e.g. an enum ``ADD VALUE`` on a missing type) before it reaches
    the deployed migrate task. ``env.py`` reads ``settings.db_url``, so the connection is
    redirected by overriding the DB settings fields. ``command.upgrade`` runs its own
    event loop, so it is executed in a worker thread to avoid nesting under the test loop.
    """
    with PostgresContainer("postgres:17", driver="psycopg") as pg:
        url = urlparse(pg.get_connection_url())
        monkeypatch.setattr(settings, "DB_HOST", url.hostname)
        monkeypatch.setattr(settings, "DB_PORT", url.port)
        monkeypatch.setattr(settings, "DB_USERNAME", url.username)
        monkeypatch.setattr(settings, "DB_PASSWORD", url.password)
        monkeypatch.setattr(settings, "DB_NAME", url.path.lstrip("/"))

        cfg = Config()
        cfg.set_main_option("script_location", "migrations")
        await anyio.to_thread.run_sync(command.upgrade, cfg, "head")
