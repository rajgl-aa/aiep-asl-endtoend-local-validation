"""Configuration settings for the Flight Disruption Assistant.

Pydantic-settings based configuration for:
- App settings (service metadata, CORS)
- Agent settings (disruption handling tuning)

All settings are loaded from environment variables using Pydantic BaseSettings,
which automatically handles type conversion and validation.
"""

from functools import lru_cache
from typing import List

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class AppSettings(BaseSettings):
    """Configuration for FastAPI application.

    These settings are loaded from environment variables automatically.
    Environment variable names are case-insensitive (e.g., APP_TITLE or app_title both work).
    """

    # ========================================================================
    # Application Metadata
    # ========================================================================
    app_title: str = Field(
        default="aiep-agent-flight-disruption",
        description="Application title shown in OpenAPI docs (from APP_TITLE)"
    )

    app_description: str = Field(
        default="Airline operations assistant for passenger rebooking, baggage tracing, and disruption notifications",
        description="Application description for OpenAPI docs (from APP_DESCRIPTION)"
    )

    app_version: str = Field(
        default="1.0.0",
        description="Application version (from APP_VERSION)"
    )

    environment: str = Field(
        default="local",
        description="Deployment environment name returned by /api/v1/status (from ENV)"
    )

    # ========================================================================
    # CORS Configuration
    # ========================================================================
    cors_origins: str = Field(
        default="http://localhost:3000,http://localhost:8000",
        description="Comma-separated list of allowed CORS origins (from CORS_ORIGINS)"
    )

    cors_allow_credentials: bool = Field(
        default=True,
        description="Whether to allow credentials in CORS requests (from CORS_ALLOW_CREDENTIALS)"
    )

    def get_cors_origins_list(self) -> List[str]:
        """Parse CORS origins string into list."""
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore"
    )


class AgentSettings(BaseSettings):
    """Configuration for the flight disruption pipeline.

    These settings are loaded from environment variables automatically.
    """

    # ========================================================================
    # Azure OpenAI Configuration (used by the full IROPS pipeline)
    # ========================================================================
    azure_openai_model: str = Field(
        default="gpt-4o-mini",
        description="Azure OpenAI model name (from AZURE_OPENAI_MODEL)"
    )

    azure_openai_api_version: str = Field(
        default="2025-01-01-preview",
        description="Azure OpenAI API version (from AZURE_OPENAI_API_VERSION)"
    )

    # ========================================================================
    # Disruption Handling Tuning
    # ========================================================================
    max_rebooking_options: int = Field(
        default=5,
        description="Maximum alternative flights offered per rebooking request (from MAX_REBOOKING_OPTIONS)",
        ge=1,
        le=20
    )

    notification_retry_count: int = Field(
        default=3,
        description="Retries for passenger notification delivery (from NOTIFICATION_RETRY_COUNT)",
        ge=0,
        le=10
    )

    hitl_required: bool = Field(
        default=True,
        description="Require human-in-the-loop confirmation before committing a rebooking (from HITL_REQUIRED)"
    )

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore"
    )


# ============================================================================
# Singleton Factory Functions
# ============================================================================


@lru_cache(maxsize=1)
def get_app_settings() -> AppSettings:
    """Get singleton AppSettings instance."""
    return AppSettings()


@lru_cache(maxsize=1)
def get_agent_settings() -> AgentSettings:
    """Get singleton AgentSettings instance."""
    return AgentSettings()
