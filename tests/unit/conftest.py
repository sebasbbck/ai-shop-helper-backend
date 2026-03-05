from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlmodel.ext.asyncio.session import AsyncSession


@pytest.fixture
def mock_session() -> AsyncMock:
    """Return a mock AsyncSession for testing.

    This fixture provides a mock AsyncSession that can be used in tests to simulate database interactions without
    requiring a real database connection. The mock session's exec method is set up to return a MagicMock, allowing
    tests to specify return values and assert calls.

    Returns:
        AsyncMock: A mock AsyncSession instance.
    """
    session = AsyncMock(spec=AsyncSession)
    exec_result = MagicMock()
    session.exec.return_value = exec_result
    return session
