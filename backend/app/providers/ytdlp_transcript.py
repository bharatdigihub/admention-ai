from __future__ import annotations

import logging

import httpx
from yt_dlp import YoutubeDL

from app.core.exceptions import TranscriptUnavailableError
from app.core.proxy import build_httpx_client, build_ytdlp_proxy_opts
from app.providers.caption_formats import parse_json3_captions
from app.providers.transcript import TranscriptCue

logger = logging.getLogger(__name__)

# Try multiple player clients in order — if the Render IP is blocked on one,
# another client type may succeed. Each entry is a list passed to player_client.
_PLAYER_CLIENT_ATTEMPTS: list[list[str]] = [
    ["ios"],
    ["android"],
    ["tv_embedded"],
    ["mweb"],
    ["ios", "android"],
]


class YtDlpTranscriptProvider:
    """Fetches timestamped captions through yt-dlp when the official transcript API is blocked.

    Tries multiple player_client configurations in order so that if one is
    rate-limited or blocked by YouTube on a cloud host, another may succeed.
    Routes all requests through the configured HTTP proxy when available.
    """

    name = "ytdlp"
    direct_youtube = True

    def __init__(self, client: httpx.Client | None = None) -> None:
        self._client = client

    def fetch(self, video_id: str) -> list[TranscriptCue]:
        last_exc: Exception | None = None

        for player_clients in _PLAYER_CLIENT_ATTEMPTS:
            try:
                caption_url = self._caption_url(video_id, player_clients)
                client = self._client or build_httpx_client(timeout=30.0, follow_redirects=True)
                owns_client = self._client is None
                try:
                    response = client.get(caption_url)
                    if response.status_code in (403, 429):
                        logger.warning(
                            "yt-dlp caption download returned HTTP %s for %s — "
                            "server IP may be blocked by YouTube.",
                            response.status_code,
                            video_id,
                        )
                        raise TranscriptUnavailableError(
                            f"YouTube blocked caption download from this server IP (HTTP {response.status_code})."
                        )
                    response.raise_for_status()
                    payload = response.json()
                finally:
                    if owns_client:
                        client.close()

                cues = parse_json3_captions(payload)
                if not cues:
                    raise TranscriptUnavailableError("The YouTube transcript was empty.")
                logger.info(
                    "yt-dlp fetched %s cues for %s using player_client=%s",
                    len(cues),
                    video_id,
                    player_clients,
                )
                return cues

            except TranscriptUnavailableError as exc:
                logger.info(
                    "yt-dlp player_client=%s failed for %s [%s]: %s",
                    player_clients,
                    video_id,
                    type(exc).__name__,
                    exc,
                )
                last_exc = exc
                continue
            except Exception as exc:
                logger.info(
                    "yt-dlp player_client=%s raised unexpected error for %s [%s]: %s",
                    player_clients,
                    video_id,
                    type(exc).__name__,
                    exc,
                )
                last_exc = exc
                continue

        raise TranscriptUnavailableError(
            f"yt-dlp exhausted all player client options for this video: "
            f"{type(last_exc).__name__}: {last_exc}"
        ) from last_exc

    def _caption_url(self, video_id: str, player_clients: list[str]) -> str:
        options: dict = {
            "skip_download": True,
            "quiet": True,
            "no_warnings": True,
            "noplaylist": True,
            "extractor_args": {
                "youtube": {
                    "player_client": player_clients,
                }
            },
            "http_headers": {
                "User-Agent": (
                    "com.google.ios.youtube/20.10.38 "
                    "(iPhone16,2; U; CPU iOS 18_1_0 like Mac OS X)"
                ),
            },
        }
        # Inject proxy into yt-dlp if configured.
        options.update(build_ytdlp_proxy_opts())

        with YoutubeDL(options) as ydl:
            info = ydl.extract_info(f"https://www.youtube.com/watch?v={video_id}", download=False)

        for source_name in ("subtitles", "automatic_captions"):
            tracks_by_lang = info.get(source_name) or {}
            track = self._pick_english_track(tracks_by_lang)
            if track and track.get("url"):
                return str(track["url"])

        raise TranscriptUnavailableError(
            f"yt-dlp (player_client={player_clients}) found no caption track for this video."
        )

    def _pick_english_track(self, tracks_by_lang: dict) -> dict | None:
        preferred = ("en", "en-US", "en-GB", "en-orig")
        for lang in preferred:
            for track in tracks_by_lang.get(lang) or []:
                if track.get("ext") == "json3" and track.get("url"):
                    return track
        for lang, tracks in tracks_by_lang.items():
            if not str(lang).startswith("en"):
                continue
            for track in tracks or []:
                if track.get("ext") == "json3" and track.get("url"):
                    return track
        for tracks in tracks_by_lang.values():
            for track in tracks or []:
                if track.get("ext") == "json3" and track.get("url"):
                    return track
        return None
