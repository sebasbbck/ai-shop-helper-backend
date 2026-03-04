from httpx import AsyncClient


class TestHealth:
    """Tests for the /health endpoint."""

    async def test_success(self, client: AsyncClient):
        """Test successful health check."""
        response = await client.get("/health")

        assert response.status_code == 200
        assert response.json() == {"status": "OK"}
