from __future__ import annotations

import httpx
from yt_dlp import YoutubeDL

from app.core.exceptions import TranscriptUnavailableError
from app.providers.caption_formats import parse_json3_captions
from app.providers.transcript import TranscriptCue


class YtDlpTranscriptProvider:
    """Fetches timestamped captions through yt-dlp when the official transcript API is blocked."""

    name = "youtube"

    def __init__(self, client: httpx.Client | None = None) -> None:
        self._client = client

    def fetch(self, video_id: str) -> list[TranscriptCue]:
        try:
            caption_url = self._caption_url(video_id)
            client = self._client or httpx.Client(timeout=30.0, follow_redirects=True)
            owns_client = self._client is None
            try:
                response = client.get(caption_url)
                response.raise_for_status()
                payload = response.json()
            finally:
                if owns_client:
                    client.close()
        except TranscriptUnavailableError:
            raise
        except Exception as exc:
            raise TranscriptUnavailableError(
                "A timestamped YouTube transcript is not available for this video."
            ) from exc

        cues = parse_json3_captions(payload)
        if not cues:
            raise TranscriptUnavailableError("The YouTube transcript was empty.")
        return cues

    def _caption_url(self, video_id: str) -> str:
        options = {
            "skip_download": True,
            "quiet": True,
            "no_warnings": True,
            "noplaylist": True,
            "extractor_args": {
                "youtube": {
                    "player_client": ["ios", "android", "tv_embedded", "web"],
                }
            },
            "http_headers": {
                "User-Agent": (
                    "com.google.ios.youtube/20.10.38 "
                    "(iPhone16,2; U; CPU iOS 18_1_0 like Mac OS X)"
                ),
            },
        }
        with YoutubeDL(options) as ydl:
            info = ydl.extract_info(f"https://www.youtube.com/watch?v={video_id}", download=False)

        for source_name in ("subtitles", "automatic_captions"):
            tracks_by_lang = info.get(source_name) or {}
            track = self._pick_english_track(tracks_by_lang)
            if track and track.get("url"):
                return str(track["url"])

        raise TranscriptUnavailableError("A timestamped YouTube transcript is not available for this video.")

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
