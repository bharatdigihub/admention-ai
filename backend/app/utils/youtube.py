import re
from datetime import datetime, timezone
from urllib.parse import parse_qs, urlparse

from app.core.exceptions import InvalidYouTubeURLError

YOUTUBE_VIDEO_ID_RE = re.compile(r"^[A-Za-z0-9_-]{11}$")
ISO_DURATION_RE = re.compile(
    r"^P(?:(?P<days>\d+)D)?T?(?:(?P<hours>\d+)H)?(?:(?P<minutes>\d+)M)?(?:(?P<seconds>\d+)S)?$"
)


def validate_youtube_url(youtube_url: str) -> str:
    """Validate a YouTube URL and return its 11-character video ID."""
    return extract_video_id(youtube_url)


def extract_video_id(youtube_url: str) -> str:
    if not youtube_url or not str(youtube_url).strip():
        raise InvalidYouTubeURLError("A YouTube URL is required.")

    raw = str(youtube_url).strip()
    parsed = urlparse(raw if "://" in raw else f"https://{raw}")
    host = (parsed.netloc or "").lower().removeprefix("www.")
    path = parsed.path or ""
    query = parse_qs(parsed.query)

    video_id: str | None = None

    if host in {"youtube.com", "m.youtube.com", "music.youtube.com", "youtube-nocookie.com"}:
        if path == "/watch" or path.startswith("/watch"):
            video_id = (query.get("v") or [None])[0]
        else:
            parts = [part for part in path.split("/") if part]
            if len(parts) >= 2 and parts[0] in {"live", "embed", "shorts", "v"}:
                video_id = parts[1]
    elif host == "youtu.be":
        parts = [part for part in path.split("/") if part]
        video_id = parts[0] if parts else None

    if not video_id or not YOUTUBE_VIDEO_ID_RE.match(video_id):
        raise InvalidYouTubeURLError("The URL is not a valid YouTube video URL.")

    return video_id


def normalize_watch_url(video_id: str) -> str:
    return f"https://www.youtube.com/watch?v={video_id}"


def timestamp_url(video_id: str, timestamp_seconds: float) -> str:
    return generate_youtube_timestamp_url(video_id, timestamp_seconds)


def generate_youtube_timestamp_url(video_id: str, timestamp_seconds: float) -> str:
    seconds = max(0, int(timestamp_seconds))
    return f"https://www.youtube.com/watch?v={video_id}&t={seconds}s"


def format_timestamp(timestamp_seconds: float) -> str:
    total = max(0, int(timestamp_seconds))
    hours, remainder = divmod(total, 3600)
    minutes, seconds = divmod(remainder, 60)
    return f"{hours:02d}:{minutes:02d}:{seconds:02d}"


def parse_iso8601_duration(value: str | None) -> int | None:
    if not value:
        return None
    match = ISO_DURATION_RE.match(value)
    if not match:
        return None
    days = int(match.group("days") or 0)
    hours = int(match.group("hours") or 0)
    minutes = int(match.group("minutes") or 0)
    seconds = int(match.group("seconds") or 0)
    return days * 86400 + hours * 3600 + minutes * 60 + seconds


def parse_published_at(value: str | None) -> datetime | None:
    if not value:
        return None
    normalized = value.replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed
