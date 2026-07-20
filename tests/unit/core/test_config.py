from ai_shop_helper_backend.core.config import Settings


class TestIsDevelopment:
    """Tests for the is_development property of Settings."""

    def test_true_for_dev(self):
        """is_development should be True when ENVIRONMENT is 'dev'."""
        assert Settings(ENVIRONMENT="dev").is_development is True

    def test_false_for_prod(self):
        """is_development should be False when ENVIRONMENT is 'prod'."""
        assert Settings(ENVIRONMENT="prod").is_development is False


class TestRefreshTokenPath:
    """Tests for the refresh_token_path property of Settings."""

    def test_is_root_regardless_of_prefix(self):
        """refresh_token_path must be '/' so proxy.ts can read the cookie on page routes."""
        assert Settings(API_V1_STR="/api/v1").refresh_token_path == "/"
        assert Settings(API_V1_STR="").refresh_token_path == "/"


class TestCorsOrigins:
    """Tests for the cors_origins property of Settings."""

    def test_dev_includes_localhost_origins(self):
        """In development environment, cors_origins should include localhost origins."""
        assert any(
            "localhost" in o
            for o in Settings(ENVIRONMENT="dev", CORS_ORIGINS="").cors_origins
        )

    def test_dev_includes_configured_origins(self):
        """In development environment, cors_origins should include configured origins."""
        assert any(
            "dev.example.com" in o
            for o in Settings(
                ENVIRONMENT="dev", CORS_ORIGINS="https://dev.example.com"
            ).cors_origins
        )

    def test_prod_excludes_localhost(self):
        """In production environment, cors_origins should not include localhost origins."""
        assert not any(
            "localhost" in o
            for o in Settings(
                ENVIRONMENT="prod", CORS_ORIGINS="https://example.com"
            ).cors_origins
        )

    def test_prod_returns_configured_origins(self):
        """In production environment, cors_origins should return configured origins."""
        origins = Settings(
            ENVIRONMENT="prod", CORS_ORIGINS="https://a.com,https://b.com"
        ).cors_origins
        assert origins == ["https://a.com", "https://b.com"]

    def test_empty_cors_origins_in_prod_returns_empty(self):
        """In production environment, if CORS_ORIGINS is empty, cors_origins should return an empty list."""
        assert Settings(ENVIRONMENT="prod", CORS_ORIGINS="").cors_origins == []


class TestDbUrl:
    """Tests for the db_url property of Settings."""

    def test_handles_special_characters(self):
        """Should url encode special characters in password and username."""
        settings = Settings(
            DB_HOST="localhost",
            DB_PORT=5432,
            DB_USERNAME="t3$t@[#u$3R]",
            DB_PASSWORD="t3$t@[#u$3R]p@$$W0rD",
            DB_NAME="testdb",
        )
        expected_url = "postgresql+psycopg://t3%24t%40%5B%23u%243R%5D:t3%24t%40%5B%23u%243R%5Dp%40%24%24W0rD@localhost:5432/testdb"
        assert str(settings.db_url) == expected_url
