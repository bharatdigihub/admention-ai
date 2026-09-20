from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=("../.env", ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "AdMention AI"
    app_env: str = "development"
    log_level: str = "INFO"

    backend_host: str = "0.0.0.0"
    backend_port: int = 8000
    backend_cors_origins: str = "http://localhost:5173,http://localhost:3000"

    database_url: str = "sqlite:///./admention.db"

    youtube_api_key: str = ""
    openai_api_key: str = ""
    openai_model: str = "gpt-4o-mini"

    whisper_enabled: bool = False
    whisper_provider: str = "mock"
    whisper_model: str = "base"
    whisper_sample_path: str = ""
    mention_context_before: int = 2
    mention_context_after: int = 2

    @property
    def cors_origins(self) -> list[str]:
        return [origin.strip() for origin in self.backend_cors_origins.split(",") if origin.strip()]

    @property
    def is_sqlite(self) -> bool:
        return self.database_url.startswith("sqlite")


@lru_cache
def get_settings() -> Settings:
    return Settings()
