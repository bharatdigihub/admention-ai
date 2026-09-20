from __future__ import annotations

import logging
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

import httpx

from app.core.exceptions import TranscriptUnavailableError
from app.providers.caption_formats import parse_caption_body
from app.providers.transcript import TranscriptCue, TranscriptProvider

logger = logging.getLogger(__name__)

PLAYER_URL = "https://www.youtube.com/youtubei/v1/player?prettyPrint=false"

# iOS InnerTube still returns caption track URLs without a PO token (2026).
IOS_CLIENT = {
    "clientName": "IOS",
    "clientVersion": "20.10.38",
    "deviceMake": "Apple",
    "deviceModel": "iPhone16,2",
    "osName": "iOS",
    "osVersion": "18.1.0",
    "hl": "en",
    "gl": "US",
    "userAgent": "com.google.ios.youtube/20.10.38 (iPhone16,2; U; CPU iOS 18_1_0 like Mac OS X)",
}

TV_EMBED_CLIENT = {
    "clientName": "TVHTML5_SIMPLY_EMBEDDED_PLAYER",
    "clientVersion": "2.0",
    "hl": "en",
    "gl": "US",
    "userAgent": "Mozilla/5.0 (ChromiumStylePlatform) Cobalt/Version",
}

PREFERRED_LANGS = ("en", "en-US", "en-GB", "en-orig", "a.en")


class InnertubeTranscriptProvider:
    """Fetches captions through YouTube InnerTube so cloud hosts can still read tracks."""

    name = "youtube"

    def __init__(self, client: httpx.Client | None = None) -> None:
        self._client = client

    def fetch(self, video_id: str) -> list[TranscriptCue]:
        client = self._client or httpx.Client(timeout=45.0, follow_redirects=True)
        owns_client = self._client is None
        try:
            tracks = self._caption_tracks(client, video_id)
            track = self._pick_track(tracks)
            if track is None:
                raise TranscriptUnavailableError(
                    "A timestamped YouTube transcript is not available for this video."
                )
            cues = self._download_cues(client, str(track["baseUrl"]))
        except TranscriptUnavailableError:
            raise
        except Exception as exc:
            logger.exception("InnerTube caption request failed for %s", video_id)
            raise TranscriptUnavailableError(
                "A timestamped YouTube transcript is not available for this video."
            ) from exc
        finally:
            if owns_client:
                client.close()

        if not cues:
            raise TranscriptUnavailableError("The YouTube transcript was empty.")
        return cues

    def _caption_tracks(self, client: httpx.Client, video_id: str) -> list[dict]:
        last_error: Exception | None = None
        for client_config in (IOS_CLIENT, TV_EMBED_CLIENT):
            try:
                payload = self._player_payload(video_id, client_config)
                headers = {
                    "Content-Type": "application/json",
                    "User-Agent": client_config["userAgent"],
                    "X-YouTube-Client-Name": "5" if client_config["clientName"] == "IOS" else "85",
                    "X-YouTube-Client-Version": client_config["clientVersion"],
                }
                response = client.post(PLAYER_URL, json=payload, headers=headers)
                response.raise_for_status()
                body = response.json()
                tracks = (
                    body.get("captions", {})
                    .get("playerCaptionsTracklistRenderer", {})
                    .get("captionTracks")
                    or []
                )
                if tracks:
                    logger.info(
                        "InnerTube %s returned %s caption tracks for %s",
                        client_config["clientName"],
                        len(tracks),
                        video_id,
                    )
                    return tracks
                status = (body.get("playabilityStatus") or {}).get("status")
                logger.info(
                    "InnerTube %s had no caption tracks for %s (playability=%s)",
                    client_config["clientName"],
                    video_id,
                    status,
                )
            except Exception as exc:
                last_error = exc
                logger.info(
                    "InnerTube %s player call failed for %s: %s",
                    client_config["clientName"],
                    video_id,
                    exc,
                )
                continue
        if last_error:
            raise last_error
        return []

    def _player_payload(self, video_id: str, client_config: dict) -> dict:
        client_body = {key: value for key, value in client_config.items() if key != "userAgent"}
        payload: dict = {
            "context": {"client": client_body},
            "videoId": video_id,
            "contentCheckOk": True,
            "racyCheckOk": True,
        }
        if client_config["clientName"] == "TVHTML5_SIMPLY_EMBEDDED_PLAYER":
            payload["context"]["thirdParty"] = {"embedUrl": "https://www.youtube.com/"}
        return payload

    def _pick_track(self, tracks: list[dict]) -> dict | None:
        def lang_of(track: dict) -> str:
            return str(track.get("languageCode") or "").lower()

        for preferred in PREFERRED_LANGS:
            for track in tracks:
                if lang_of(track) == preferred.lower() and track.get("baseUrl"):
                    return track
        for track in tracks:
            if lang_of(track).startswith("en") and track.get("baseUrl"):
                return track
        for track in tracks:
            if track.get("baseUrl"):
                return track
        return None

    def _download_cues(self, client: httpx.Client, base_url: str) -> list[TranscriptCue]:
        json_url = _with_fmt(base_url, "json3")
        response = client.get(
            json_url,
            headers={"User-Agent": IOS_CLIENT["userAgent"]},
        )
        response.raise_for_status()
        cues = parse_caption_body(response.text)
        if cues:
            return cues
        xml_url = _with_fmt(base_url, "srv3")
        xml_response = client.get(
            xml_url,
            headers={"User-Agent": IOS_CLIENT["userAgent"]},
        )
        xml_response.raise_for_status()
        return parse_caption_body(xml_response.text)


def _with_fmt(url: str, fmt: str) -> str:
    parts = urlsplit(url)
    query = [(key, value) for key, value in parse_qsl(parts.query, keep_blank_values=True) if key != "fmt"]
    query.append(("fmt", fmt))
    return urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(query), parts.fragment))


def get_innertube_transcript_provider() -> TranscriptProvider:
    return InnertubeTranscriptProvider()
