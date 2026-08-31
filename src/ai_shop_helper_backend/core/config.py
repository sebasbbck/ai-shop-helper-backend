from typing import Annotated, Literal
from urllib.parse import quote_plus

from pydantic import (
    AnyUrl,
    BeforeValidator,
    Field,
    PostgresDsn,
    computed_field,
    model_validator,
)
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
        BACKEND_URL (str): The backend base URL including /api/v1 for webhook callbacks.
        CRYPTOGRAPHIC_KEY (str): Key deriving the Fernet cipher for encrypting connection secrets at rest.
        CALLBACK_API_WORDPRESS_URL (str): Full URL the plugin redirects to after approval.
        WP_SUCCESS_FRONTEND_URL (str): Frontend URL shown after successful WP connection.
        WP_ERROR_FRONTEND_URL (str): Frontend URL shown when WP connection fails.
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
    FIRST_SUPERUSER_EMAIL: str = "admin@aishophelper.ai"
    FIRST_SUPERUSER_PASSWORD: str = "changethis"
    # Database
    DB_HOST: str = Field(default=...)
    DB_PORT: int = Field(default=...)
    DB_USERNAME: str = Field(default=...)
    DB_PASSWORD: str = Field(default=...)
    DB_NAME: str = Field(default=...)
    # Webhooks
    N8N_URL: str = Field(default=...)
    BACKEND_URL: str = Field(default=...)
    # WordPress connection (demo — removable)
    CRYPTOGRAPHIC_KEY: str = Field(default=...)
    CALLBACK_API_WORDPRESS_URL: str = (
        "http://localhost:8080/api/v1/connections/wordpress/callback"
    )
    WP_SUCCESS_FRONTEND_URL: str = "http://localhost:3000/connection/success"
    WP_ERROR_FRONTEND_URL: str = "http://localhost:3000/connection/failure"
    # Stripe
    STRIPE_SECRET_KEY: str = ""
    STRIPE_WEBHOOK_SECRET: str = ""
    FRONTEND_URL: str = "http://localhost:3000"
    # Notifuse
    NOTIFUSE_BASE_URL: str = ""
    NOTIFUSE_WORKSPACE_ID: str = ""
    NOTIFUSE_API_KEY: str = ""
    # Email
    EMAIL_VERIFY_TTL_HOURS: int = 24
    EMAIL_RESET_TTL_MINUTES: int = 60
    EMAIL_RESEND_COOLDOWN_S: int = 60
    EMAIL_RESEND_MAX_PER_HOUR: int = 5
    EMAIL_POLL_INTERVAL_S: int = 5
    EMAIL_MAX_ATTEMPTS: int = 6
    # Google OAuth — login
    GOOGLE_CLIENT_ID: str = Field(default=...)
    GOOGLE_CLIENT_SECRET: str = Field(default=...)
    GOOGLE_LOGIN_REDIRECT_URI: str = "http://localhost:8080/api/v1/google/callback"
    GOOGLE_LOGIN_SUCCESS_URL: str = "http://localhost:3000/login/success"
    GOOGLE_LOGIN_ERROR_URL: str = "http://localhost:3000/login/failure"
    # Google OAuth — project connection (GA4 / Search Console data)
    GOOGLE_CONNECTION_REDIRECT_URI: str = (
        "http://localhost:8080/api/v1/connections/google/callback"
    )
    # Other
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
    def billing_success_url(self) -> str:
        """Public frontend return route after a successful checkout.

        A single public bounce route (outside the auth-gated group) that
        re-enters the app same-site, so the SameSite=Strict refresh cookie is
        not lost on the cross-site return from Stripe.
        """
        return f"{self.FRONTEND_URL.rstrip('/')}/billing/return?status=success&session_id={{CHECKOUT_SESSION_ID}}"

    @computed_field
    @property
    def billing_cancel_url(self) -> str:
        """Public frontend return route when checkout is cancelled."""
        return f"{self.FRONTEND_URL.rstrip('/')}/billing/return?status=cancel"

    @computed_field
    @property
    def stripe_portal_return_url(self) -> str:
        """Public frontend return route the Stripe customer portal returns to."""
        return f"{self.FRONTEND_URL.rstrip('/')}/billing/return?status=portal"

    @model_validator(mode="after")
    def _require_secrets_in_prod(self) -> "Settings":
        """Fail fast in production if required secrets are missing.

        Empty defaults are allowed in development so the backend boots and tests
        run without live accounts; production must not start without them.
        """
        if self.ENVIRONMENT.lower() == "prod" and not (
            self.STRIPE_SECRET_KEY
            and self.STRIPE_WEBHOOK_SECRET
            and self.NOTIFUSE_API_KEY
        ):
            raise ValueError(
                "STRIPE_SECRET_KEY, STRIPE_WEBHOOK_SECRET, and NOTIFUSE_API_KEY are required in production"
            )
        return self

    @computed_field
    @property
    def refresh_token_path(self) -> str:
        """Cookie path for the refresh token.

        Must be '/' so proxy.ts can read the cookie on page routes.

        Returns:
            str: The cookie path for the refresh token.
        """
        return "/"

    @computed_field
    @property
    def db_url(self) -> PostgresDsn:
        """Construct the database URL from the individual database settings.

        Returns:
            PostgresDsn: The constructed database URL.
        """
        return PostgresDsn.build(
            scheme="postgresql+psycopg",
            username=quote_plus(self.DB_USERNAME),
            password=quote_plus(self.DB_PASSWORD),
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
