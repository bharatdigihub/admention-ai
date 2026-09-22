from __future__ import annotations

import logging

import httpx

from app.core.config import get_settings
from app.core.exceptions import TranscriptUnavailableError
from app.providers.transcript import TranscriptCue

logger = logging.getLogger(__name__)

_BROWSER_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json,text/html;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": "https://adverify.codewithbharat.dev/",
}


class HostingerCaptionProxyProvider:
    """Asks Hostinger PHP to fetch YouTube captions so Render's blocked IP is not used."""

    name = "hostinger_proxy"
    direct_youtube = False

    def __init__(self, client: httpx.Client | None = None, proxy_url: str | None = None) -> None:
        self._client = client
        self._proxy_url = proxy_url

    def fetch(self, video_id: str) -> list[TranscriptCue]:
        url = (self._proxy_url if self._proxy_url is not None else get_settings().caption_proxy_url).strip()
        if not url:
            raise TranscriptUnavailableError("Hostinger caption proxy is not configured.")

        client = self._client or httpx.Client(
            timeout=45.0,
            follow_redirects=True,
            headers=_BROWSER_HEADERS,
        )
        owns_client = self._client is None
        try:
            response = client.get(url, params={"v": video_id}, headers=_BROWSER_HEADERS)
        except Exception as exc:
            raise TranscriptUnavailableError(f"Hostinger caption proxy request failed: {exc}") from exc
        finally:
            if owns_client:
                client.close()

        if response.status_code >= 400:
            detail = _error_detail(response)
            raise TranscriptUnavailableError(
                f"Hostinger caption proxy HTTP {response.status_code}{detail}"
            )

        payload = response.json() if _looks_json(response) else None
        if not isinstance(payload, dict):
            raise TranscriptUnavailableError(
                "Hostinger caption proxy did not return JSON. Upload caption-proxy.php to /adverify."
            )
        segments = payload.get("segments")
        if not isinstance(segments, list) or not segments:
            raise TranscriptUnavailableError("Hostinger caption proxy returned no caption segments.")

        cues = [
            TranscriptCue(
                start=float(item.get("start") or 0),
                duration=float(item.get("duration") or 0),
                text=str(item.get("text") or "").strip(),
            )
            for item in segments
            if isinstance(item, dict) and str(item.get("text") or "").strip()
        ]
        if not cues:
            raise TranscriptUnavailableError("Hostinger caption proxy returned empty caption text.")
        logger.info("Hostinger caption proxy returned %s cues for %s", len(cues), video_id)
        return cues


def _looks_json(response: httpx.Response) -> bool:
    ctype = (response.headers.get("content-type") or "").lower()
    return "json" in ctype or response.text.lstrip().startswith("{")


def _error_detail(response: httpx.Response) -> str:
    try:
        payload = response.json()
    except Exception:
        return ""
    if isinstance(payload, dict) and payload.get("error"):
        return f": {payload['error']}"
    return ""


def get_hostinger_caption_proxy_provider() -> HostingerCaptionProxyProvider:
    return HostingerCaptionProxyProvider()
