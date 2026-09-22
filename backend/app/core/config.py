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
    backend_cors_origins: str = "http://localhost:5173,http://localhost:3000,https://adverify.codewithbharat.dev"

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

    # Caption mirrors used when YouTube blocks datacenter IPs (Render, etc.).
    invidious_instances: str = "https://inv.nadeko.net"
    piped_instances: str = "https://api.piped.private.coffee"

    # -------------------------------------------------------------------
    # Proxy configuration (for bypassing YouTube datacenter IP blocks)
    # -------------------------------------------------------------------
    # Generic HTTP proxy URL — used by httpx (InnerTube, yt-dlp download)
    # and youtube-transcript-api.  Example:
    #   http://user:password@proxy-host:port
    # Set this in the Render dashboard (or .env locally) to route all
    # YouTube requests through a residential proxy.
    http_proxy: str = ""

    # Webshare-specific credentials (youtube-transcript-api has native support).
    # If set, these take priority over http_proxy for youtube-transcript-api.
    # Get these from https://dashboard.webshare.io/proxy/settings
    webshare_proxy_username: str = ""
    webshare_proxy_password: str = ""

    @property
    def cors_origins(self) -> list[str]:
        return [origin.strip() for origin in self.backend_cors_origins.split(",") if origin.strip()]

    @property
    def is_sqlite(self) -> bool:
        return self.database_url.startswith("sqlite")

    @property
    def proxy_url(self) -> str | None:
        """Return a usable HTTP proxy URL, or None if no proxy is configured."""
        url = self.http_proxy.strip()
        return url if url else None

    @property
    def has_webshare(self) -> bool:
        return bool(self.webshare_proxy_username.strip() and self.webshare_proxy_password.strip())


@lru_cache
def get_settings() -> Settings:
    return Settings()
