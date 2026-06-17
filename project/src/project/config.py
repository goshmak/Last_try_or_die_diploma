from pathlib import Path
from typing import Optional

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

# === Application configuration ===
# Values are read from environment variables (case-insensitive) or from a .env file in the project root directory.
class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=Path(__file__).parent / ".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ------------------------------------------------------------------
    # Database
    # ------------------------------------------------------------------
    DATABASE_URL: str = Field(
        default="sqlite+aiosqlite:///./notifications.db",
        description="Async SQLAlchemy connection URL.",
    )
    # For debugging
    DB_ECHO: bool = Field(
        default=False,
        description="Log all SQL statements (useful for development).",
    )

    # ------------------------------------------------------------------
    # Redis
    # ------------------------------------------------------------------
    REDIS_URL: str = Field(
        default="redis://localhost:6379/0",
        description="Redis connection URL used for the task queue.",
    )
    REDIS_QUEUE_NAME: str = Field(
        default="notifications",
        description="Redis list key used as the notification queue.",
    )

    # ------------------------------------------------------------------
    # Worker
    # ------------------------------------------------------------------
    WORKER_CONCURRENCY: int = Field(
        default=4,
        description="Number of concurrent notification workers.",
    )
    MAX_RETRY_ATTEMPTS: int = Field(
        default=5,
        description="Maximum delivery attempts before marking a task FAILED.",
    )
    RETRY_BASE_DELAY: float = Field(
        default=2.0,
        description="Base delay (seconds) for exponential backoff. Delay = base ** attempt.",
    )

    # ------------------------------------------------------------------
    # Email (SMTP)
    # ------------------------------------------------------------------
    SMTP_HOST: str = Field(
        default="smtp.yandex.ru",
        description="SMTP server hostname.",
    )
    SMTP_PORT: int = Field(
        default=465,
        description="SMTP server port (465 for SSL, 587 for STARTTLS).",
    )
    SMTP_USE_SSL: bool = Field(
        default=True,
        description="Use SSL for SMTP connection (True for port 465).",
    )
    SMTP_USERNAME: str = Field(
        default="",
        description="SMTP authentication username (usually the sender email).",
    )
    SMTP_PASSWORD: str = Field(
        default="",
        description="SMTP authentication password or app-specific password.",
    )
    SMTP_FROM_NAME: str = Field(
        default="Humanitarian University",
        description="Display name shown in the From field.",
    )
    SMTP_FROM_EMAIL: str = Field(
        default="",
        description="Sender email address.",
    )

    # ------------------------------------------------------------------
    # VK Messaging API
    # ------------------------------------------------------------------
    VK_API_TOKEN: str = Field(
        default="",
        description="VK community API token with messages permission.",
    )
    VK_API_VERSION: str = Field(
        default="5.199",
        description="VK API version string.",
    )
    VK_GROUP_ID: str = Field(
        default="",
        description="VK community (group) ID from which messages are sent.",
    )
    VK_PEER_ID_OFFSET: int = Field(
        default=0,
        description=(
            "Offset added to group chat IDs when sending to group chats. "
            "For direct user messages set to 0."
        ),
    )

    # ------------------------------------------------------------------
    # API Gateway (upstream service)
    # ------------------------------------------------------------------
    API_GATEWAY_BASE_URL: str = Field(
        default="http://localhost:8000",
        description=(
            "Base URL of the API Gateway. Used to fetch user and assignment "
            "data when it is not included in the notification request."
        ),
    )
    API_GATEWAY_TIMEOUT: float = Field(
        default=10.0,
        description="HTTP timeout (seconds) for API Gateway requests.",
    )

    # ------------------------------------------------------------------
    # Application
    # ------------------------------------------------------------------
    APP_HOST: str = Field(default="0.0.0.0", description="Bind host for uvicorn.")
    APP_PORT: int = Field(default=8001, description="Bind port for uvicorn.")
    LOG_LEVEL: str = Field(default="INFO", description="Python logging level.")
    TEMPLATES_DIR: str = Field(
        default="templates",
        description="Directory containing Jinja2 email/VK message templates.",
    )


# Singleton — imported everywhere as `from config import settings`
settings = Settings()
