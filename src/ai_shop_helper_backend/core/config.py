from typing import Annotated, Literal

from pydantic import AnyUrl, BeforeValidator, Field, PostgresDsn, computed_field
from pydantic_settings import BaseSettings, SettingsConfigDict

from ai_shop_helper_backend.core.utils import parse_urls


class Settings(BaseSettings):
    """Application settings loaded from environment variables.

    Attributes:
        PROJECT_NAME (str): The name of the project.
        ENVIRONMENT (Literal["dev", "prod"]): The environment the application is running in.
        API_V1_STR (str): The base URL for the API.
        SECRET_KEY (str): The secret key used for security purposes.
        ACCESS_TOKEN_EXPIRE_MINUTES (int): The expiration time for access tokens in minutes.
        REFRESH_TOKEN_EXPIRE_DAYS (int): The expiration time for refresh tokens in days.
        REFRESH_TOKEN_COOKIE (str): The name of the cookie to store the refresh token.
        DB_HOST (str): The database host.
        DB_PORT (int): The database port.
        DB_USERNAME (str): The database username.
        DB_PASSWORD (str): The database password.
        DB_NAME (str): The database name.
        N8N_URL (str): The URL for n8n workflow automation tool.
        CORS_ORIGINS (list[AnyUrl]): A list of allowed origins for CORS.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_ignore_empty=True,
        extra="ignore",
    )

    # General
    PROJECT_NAME: str = "AI Shop Helper"
    ENVIRONMENT: Literal["dev", "prod"] = "dev"
    API_V1_STR: str = "/api/v1"
    # Security
    SECRET_KEY: str = Field(default=...)
    KEY_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 30
    REFRESH_TOKEN_COOKIE: str = "refresh_token"
    # Database
    DB_HOST: str = Field(default=...)
    DB_PORT: int = Field(default=...)
    DB_USERNAME: str = Field(default=...)
    DB_PASSWORD: str = Field(default=...)
    DB_NAME: str = Field(default=...)
    # Other
    N8N_URL: str = Field(default=...)
    CORS_ORIGINS: Annotated[
        list[AnyUrl],
        BeforeValidator(parse_urls),
    ] = []
    _DEV_ORIGINS: Annotated[
        list[AnyUrl],
        BeforeValidator(parse_urls),
    ] = [
        AnyUrl("http://localhost:3000"),
    ]

    @computed_field
    @property
    def refresh_token_path(self) -> str:
        """Construct the path for the refresh token endpoint.

        Returns:
            str: The path for the refresh token endpoint.
        """
        return f"{self.API_V1_STR}/auth/refresh"

    @computed_field
    @property
    def db_url(self) -> PostgresDsn:
        """Construct the database URL from the individual database settings.

        Returns:
            PostgresDsn: The constructed database URL.
        """
        return PostgresDsn.build(
            scheme="postgresql+psycopg",
            username=self.DB_USERNAME,
            password=self.DB_PASSWORD,
            host=self.DB_HOST,
            port=self.DB_PORT,
            path=self.DB_NAME,
        )

    @computed_field
    @property
    def is_development(self) -> bool:
        """Check if the application is running in development environment.

        Returns:
            bool: True if the application is running in development environment, False otherwise.
        """
        return self.ENVIRONMENT.lower() == "dev"

    @computed_field
    @property
    def cors_origins(self) -> list[str]:
        """Get the list of allowed origins for CORS, including development defaults if in development environment.

        Returns:
            list[str]: The list of allowed origins for CORS.
        """
        origins = set(self.CORS_ORIGINS)
        if self.is_development:
            origins = list(origins.union(set(self._DEV_ORIGINS)))
        return list(map(lambda x: str(x).rstrip("/"), origins))


settings = Settings()
