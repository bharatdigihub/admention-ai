"""
Shared proxy helpers used by all transcript providers.

Reads proxy configuration from Settings and builds the correct client objects
for httpx (InnerTube, yt-dlp caption download) and youtube-transcript-api.
"""
from __future__ import annotations

import logging

import httpx

from app.core.config import get_settings

logger = logging.getLogger(__name__)


def get_proxy_url() -> str | None:
    """Return the configured HTTP proxy URL, or None."""
    return get_settings().proxy_url


def build_httpx_client(**kwargs) -> httpx.Client:
    """
    Build an httpx.Client.  If HTTP_PROXY is configured the client routes all
    requests through it, so YouTube sees a residential IP instead of Render's
    datacenter IP.
    """
    proxy = get_proxy_url()
    if proxy:
        kwargs.setdefault("proxy", proxy)
        logger.debug("httpx client will use proxy: %s", _redact(proxy))
    return httpx.Client(**kwargs)


def build_yta_proxy_config():
    """
    Build the best ProxyConfig for youtube-transcript-api, in priority order:
      1. WebshareProxyConfig  — if WEBSHARE_PROXY_USERNAME + PASSWORD are set
      2. GenericProxyConfig   — if HTTP_PROXY is set
      3. None                 — no proxy configured (Render IP will be used)
    """
    from youtube_transcript_api.proxies import GenericProxyConfig, WebshareProxyConfig

    settings = get_settings()

    if settings.has_webshare:
        logger.info(
            "youtube-transcript-api will use Webshare proxy (user=%s)",
            settings.webshare_proxy_username,
        )
        return WebshareProxyConfig(
            proxy_username=settings.webshare_proxy_username.strip(),
            proxy_password=settings.webshare_proxy_password.strip(),
        )

    proxy = get_proxy_url()
    if proxy:
        logger.info("youtube-transcript-api will use generic proxy: %s", _redact(proxy))
        return GenericProxyConfig(http_url=proxy, https_url=proxy)

    return None


def build_ytdlp_proxy_opts() -> dict:
    """Return a dict with the 'proxy' key set if a proxy is configured, else {}."""
    proxy = get_proxy_url()
    if proxy:
        logger.debug("yt-dlp will use proxy: %s", _redact(proxy))
        return {"proxy": proxy}
    return {}


def _redact(url: str) -> str:
    """Hide the password in a proxy URL for safe logging."""
    try:
        from urllib.parse import urlsplit, urlunsplit
        parts = urlsplit(url)
        if parts.password:
            netloc = parts.hostname or ""
            if parts.username:
                netloc = f"{parts.username}:***@{netloc}"
            if parts.port:
                netloc = f"{netloc}:{parts.port}"
            return urlunsplit((parts.scheme, netloc, parts.path, parts.query, parts.fragment))
    except Exception:
        pass
    return url
