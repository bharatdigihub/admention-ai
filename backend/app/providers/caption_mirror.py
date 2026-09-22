from __future__ import annotations

import logging
from urllib.parse import parse_qsl, quote, urlencode, urljoin, urlsplit, urlunsplit

import httpx

from app.core.config import get_settings
from app.core.exceptions import TranscriptUnavailableError
from app.core.proxy import build_httpx_client
from app.providers.caption_formats import parse_caption_body
from app.providers.transcript import TranscriptCue

logger = logging.getLogger(__name__)

_CHROME_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
)
_HEADERS = {
    "User-Agent": _CHROME_UA,
    "Accept": "application/json, text/vtt, text/xml, */*",
    "Accept-Language": "en-US,en;q=0.9",
}


class CaptionMirrorTranscriptProvider:
    """Loads captions through Invidious/Piped when YouTube blocks cloud IPs such as Render."""

    name = "captions_mirror"
    direct_youtube = False

    def __init__(
        self,
        client: httpx.Client | None = None,
        invidious_bases: list[str] | None = None,
        piped_bases: list[str] | None = None,
    ) -> None:
        self._client = client
        settings = get_settings()
        self._invidious = invidious_bases or _split_urls(settings.invidious_instances)
        self._piped = piped_bases or _split_urls(settings.piped_instances)

    def fetch(self, video_id: str) -> list[TranscriptCue]:
        client = self._client or build_httpx_client(timeout=12.0, follow_redirects=True, headers=_HEADERS)
        owns_client = self._client is None
        errors: list[str] = []
        try:
            for base in self._invidious:
                try:
                    cues = self._fetch_invidious(client, base, video_id)
                    if cues:
                        logger.info(
                            "Caption mirror Invidious %s returned %s cues for %s",
                            base,
                            len(cues),
                            video_id,
                        )
                        return cues
                except Exception as exc:
                    errors.append(f"invidious {base}: {_sanitize_error(str(exc))}")
                    logger.info("Invidious %s failed for %s [%s]: %s", base, video_id, type(exc).__name__, exc)

            for base in self._piped:
                try:
                    cues = self._fetch_piped(client, base, video_id)
                    if cues:
                        logger.info(
                            "Caption mirror Piped %s returned %s cues for %s",
                            base,
                            len(cues),
                            video_id,
                        )
                        return cues
                except Exception as exc:
                    errors.append(f"piped {base}: {_sanitize_error(str(exc))}")
                    logger.info("Piped %s failed for %s [%s]: %s", base, video_id, type(exc).__name__, exc)
        finally:
            if owns_client:
                client.close()

        detail = "; ".join(errors[:4]) if errors else "no caption-mirror instances configured"
        raise TranscriptUnavailableError(
            "Public caption hosts are blocked or busy for this video. "
            f"{_sanitize_error(detail)}"
        )

    def _fetch_invidious(self, client: httpx.Client, base: str, video_id: str) -> list[TranscriptCue]:
        listing = client.get(f"{base.rstrip('/')}/api/v1/captions/{video_id}")
        payload = _json_or_none(listing)
        blocked = _host_block_reason(payload)
        if blocked:
            raise TranscriptUnavailableError(blocked)
        listing.raise_for_status()
        if not isinstance(payload, dict) and not isinstance(payload, list):
            raise TranscriptUnavailableError("Invidious returned a non-JSON caption listing.")
        tracks = payload.get("captions") if isinstance(payload, dict) else payload
        if not isinstance(tracks, list) or not tracks:
            raise TranscriptUnavailableError("Invidious returned no caption tracks.")

        for track in _rank_caption_tracks(tracks):
            url = str(track.get("url") or "")
            if not url:
                label = track.get("label")
                lang = track.get("languageCode") or track.get("lang")
                if label:
                    url = f"/api/v1/captions/{video_id}?label={quote(str(label))}"
                elif lang:
                    url = f"/api/v1/captions/{video_id}?lang={quote(str(lang))}"
            if not url:
                continue
            response = client.get(urljoin(base.rstrip("/") + "/", url.lstrip("/")))
            if response.status_code >= 400 or not response.text.strip():
                continue
            cues = parse_caption_body(response.text)
            if cues:
                return cues
        raise TranscriptUnavailableError("Invidious caption files were empty.")

    def _fetch_piped(self, client: httpx.Client, base: str, video_id: str) -> list[TranscriptCue]:
        response = client.get(f"{base.rstrip('/')}/streams/{video_id}")
        payload = _json_or_none(response)
        blocked = _host_block_reason(payload)
        if blocked:
            raise TranscriptUnavailableError(blocked)
        response.raise_for_status()
        tracks = payload.get("subtitles") if isinstance(payload, dict) else None
        if not isinstance(tracks, list) or not tracks:
            raise TranscriptUnavailableError("Piped returned no subtitle tracks.")

        for track in _rank_caption_tracks(tracks):
            url = str(track.get("url") or "")
            if not url:
                continue
            for fmt in ("json3", "vtt", "srv3", "ttml"):
                formatted = _with_fmt(url, fmt)
                caption = client.get(formatted)
                if caption.status_code >= 400 or not caption.text.strip():
                    continue
                cues = parse_caption_body(caption.text)
                if cues:
                    return cues
        raise TranscriptUnavailableError("Piped subtitle files were empty.")


def _rank_caption_tracks(tracks: list[dict]) -> list[dict]:
    def score(track: dict) -> tuple[int, int]:
        label = str(track.get("label") or track.get("name") or "").lower()
        lang = str(track.get("languageCode") or track.get("code") or track.get("lang") or "").lower()
        auto = bool(track.get("autoGenerated")) or "auto" in label
        if lang in {"en", "en-us", "en-gb", "en-orig"} or label.startswith("english"):
            return (0, 1 if auto else 0)
        if lang.startswith("en") or "english" in label:
            return (1, 1 if auto else 0)
        return (2, 1 if auto else 0)

    return sorted(tracks, key=score)


def _split_urls(raw: str) -> list[str]:
    return [part.strip().rstrip("/") for part in (raw or "").split(",") if part.strip()]


def _json_or_none(response: httpx.Response) -> object | None:
    try:
        return response.json()
    except Exception:
        return None


def _host_block_reason(payload: object) -> str | None:
    if not isinstance(payload, dict):
        return None
    if payload.get("subtitles") or payload.get("captions") or payload.get("events"):
        return None
    blob = " ".join(str(payload.get(key) or "") for key in ("error", "message", "errorMessage"))
    lower = blob.lower()
    if any(token in lower for token in ("login_required", "not a bot", "signinconfirm", "confirm that you're not a bot")):
        return "YouTube bot-check blocked this caption host."
    if payload.get("error") or payload.get("message"):
        message = str(payload.get("message") or payload.get("error"))
        return _sanitize_error(message.split("\n", 1)[0])
    return None


def _sanitize_error(message: str) -> str:
    first = message.split("\n", 1)[0].strip()
    if "org.schabi" in first or "at org." in first:
        return "YouTube bot-check blocked this caption host."
    return first[:220]


def _with_fmt(url: str, fmt: str) -> str:
    parts = urlsplit(url)
    query = [(key, value) for key, value in parse_qsl(parts.query, keep_blank_values=True) if key != "fmt"]
    query.append(("fmt", fmt))
    return urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(query), parts.fragment))


def get_caption_mirror_transcript_provider() -> CaptionMirrorTranscriptProvider:
    return CaptionMirrorTranscriptProvider()
