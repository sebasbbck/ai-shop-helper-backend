from unittest.mock import AsyncMock, patch

from fastapi import FastAPI

from ai_shop_helper_backend.main import lifespan


class TestLifespan:
    """Tests for the lifespan context manager in main.py."""

    async def test_disposes_engine_on_shutdown(self):
        """Test that the database engine is disposed on shutdown."""
        with patch("ai_shop_helper_backend.main.engine") as mock_engine:
            mock_engine.dispose = AsyncMock()
            async with lifespan(FastAPI()):
                pass
            mock_engine.dispose.assert_awaited_once()
