from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from typing import Any, Protocol

import httpx

from app.core.config import get_settings
from app.core.exceptions import ExternalServiceError, VideoNotFoundError, YouTubeTimeoutError
from app.utils.youtube import normalize_watch_url, parse_iso8601_duration

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class VideoMetadata:
    video_id: str
    title: str | None
    channel: str | None
    published_at: str | None
    duration_seconds: int | None
    thumbnail_url: str | None


class VideoMetadataProvider(Protocol):
    def fetch(self, video_id: str) -> VideoMetadata: ...


class YouTubeProvider:
    """Retrieves public video metadata via oEmbed, optionally enriched with the Data API.

    The YouTube Data API key stays server-side (`YOUTUBE_API_KEY`). When it is
    absent, oEmbed still returns real title, channel, and thumbnail values.
    Duration and published date require the Data API and remain unset without a key.
    """

    OEMBED_URL = "https://www.youtube.com/oembed"
    DATA_API_URL = "https://www.googleapis.com/youtube/v3/videos"
    REQUEST_TIMEOUT = 15.0

    def __init__(self, client: httpx.Client | None = None, api_key: str | None = None) -> None:
        self._client = client
        self._api_key = api_key if api_key is not None else get_settings().youtube_api_key

    def fetch(self, video_id: str) -> VideoMetadata:
        client = self._client or httpx.Client(timeout=self.REQUEST_TIMEOUT)
        owns_client = self._client is None
        try:
            metadata = self._fetch_oembed(client, video_id)
            if self._api_key:
                metadata = self._enrich_with_data_api(client, metadata)
            return metadata
        finally:
            if owns_client:
                client.close()

    def _fetch_oembed(self, client: httpx.Client, video_id: str) -> VideoMetadata:
        try:
            response = client.get(
                self.OEMBED_URL,
                params={"url": normalize_watch_url(video_id), "format": "json"},
            )
        except httpx.TimeoutException as exc:
            logger.exception("YouTube oEmbed timed out for video_id=%s", video_id)
            raise YouTubeTimeoutError() from exc
        except httpx.HTTPError as exc:
            logger.exception("YouTube oEmbed request failed for video_id=%s", video_id)
            raise ExternalServiceError("Unable to reach YouTube to load video metadata.") from exc

        if response.status_code in {401, 403}:
            logger.info("YouTube oEmbed denied access for video_id=%s status=%s", video_id, response.status_code)
            raise VideoNotFoundError("This video is private or unavailable.")
        if response.status_code in {400, 404}:
            logger.info("YouTube oEmbed returned %s for video_id=%s", response.status_code, video_id)
            raise VideoNotFoundError("This video was not found or has been deleted.")
        if response.status_code >= 400:
            logger.warning(
                "YouTube oEmbed rejected metadata request video_id=%s status=%s body=%s",
                video_id,
                response.status_code,
                response.text[:500],
            )
            raise ExternalServiceError("YouTube rejected the metadata request.")

        payload = _parse_json(response, video_id)
        if not isinstance(payload, dict):
            logger.warning("YouTube oEmbed returned a non-object payload for video_id=%s", video_id)
            raise ExternalServiceError("YouTube returned an unexpected response.")

        return VideoMetadata(
            video_id=video_id,
            title=_optional_str(payload.get("title")),
            channel=_optional_str(payload.get("author_name")),
            published_at=None,
            duration_seconds=None,
            thumbnail_url=_optional_str(payload.get("thumbnail_url")),
        )

    def _enrich_with_data_api(self, client: httpx.Client, metadata: VideoMetadata) -> VideoMetadata:
        try:
            response = client.get(
                self.DATA_API_URL,
                params={
                    "id": metadata.video_id,
                    "part": "snippet,contentDetails,status",
                    "key": self._api_key,
                },
            )
        except httpx.TimeoutException:
            logger.warning("YouTube Data API timed out for video_id=%s; keeping oEmbed metadata", metadata.video_id)
            return metadata
        except httpx.HTTPError:
            logger.warning("YouTube Data API request failed for video_id=%s; keeping oEmbed metadata", metadata.video_id)
            return metadata

        if _is_quota_error(response):
            logger.warning("YouTube Data API quota exceeded for video_id=%s; keeping oEmbed metadata", metadata.video_id)
            return metadata

        if response.status_code >= 400:
            logger.warning(
                "YouTube Data API enrichment failed video_id=%s status=%s body=%s",
                metadata.video_id,
                response.status_code,
                response.text[:500],
            )
            return metadata

        try:
            payload = _parse_json(response, metadata.video_id)
        except ExternalServiceError:
            logger.warning("YouTube Data API returned malformed JSON for video_id=%s", metadata.video_id)
            return metadata

        if not isinstance(payload, dict):
            logger.warning("YouTube Data API returned a non-object payload for video_id=%s", metadata.video_id)
            return metadata

        items = payload.get("items") or []
        if not items:
            logger.info("YouTube Data API returned no items for video_id=%s", metadata.video_id)
            raise VideoNotFoundError("This video was not found, is private, or has been deleted.")

        item = items[0]
        if not isinstance(item, dict):
            logger.warning("YouTube Data API item was malformed for video_id=%s", metadata.video_id)
            return metadata

        snippet = item.get("snippet") or {}
        details = item.get("contentDetails") or {}
        status = item.get("status") or {}
        if not isinstance(snippet, dict) or not isinstance(details, dict) or not isinstance(status, dict):
            logger.warning("YouTube Data API fields were malformed for video_id=%s", metadata.video_id)
            return metadata

        privacy = status.get("privacyStatus")
        if privacy in {"private", "privacyStatusUnspecified"}:
            raise VideoNotFoundError("This video is private or unavailable.")

        return VideoMetadata(
            video_id=metadata.video_id,
            title=_optional_str(snippet.get("title")) or metadata.title,
            channel=_optional_str(snippet.get("channelTitle")) or metadata.channel,
            published_at=_optional_str(snippet.get("publishedAt")),
            duration_seconds=parse_iso8601_duration(_optional_str(details.get("duration"))),
            thumbnail_url=_best_thumbnail(snippet.get("thumbnails")) or metadata.thumbnail_url,
        )


YouTubeMetadataProvider = YouTubeProvider


def _parse_json(response: httpx.Response, video_id: str) -> Any:
    try:
        return response.json()
    except (ValueError, json.JSONDecodeError) as exc:
        logger.warning("Malformed YouTube JSON for video_id=%s body=%s", video_id, response.text[:500])
        raise ExternalServiceError("YouTube returned an unexpected response.") from exc


def _is_quota_error(response: httpx.Response) -> bool:
    if response.status_code not in {403, 429}:
        return False
    try:
        payload = response.json()
    except (ValueError, json.JSONDecodeError):
        return False
    if not isinstance(payload, dict):
        return False
    error = payload.get("error") or {}
    if not isinstance(error, dict):
        return "quota" in str(payload).lower()
    errors = error.get("errors") or []
    reasons = [str(item.get("reason", "")).lower() for item in errors if isinstance(item, dict)]
    message = str(error.get("message", "")).lower()
    return any("quota" in reason for reason in reasons) or "quota" in message


def _optional_str(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _best_thumbnail(thumbnails: object) -> str | None:
    if not isinstance(thumbnails, dict):
        return None
    for key in ("maxres", "standard", "high", "medium", "default"):
        entry = thumbnails.get(key) or {}
        if isinstance(entry, dict):
            url = entry.get("url")
            if url:
                return str(url)
    return None
