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


# Singleton — imported everywhere as `from config import settings`
settings = Settings()
