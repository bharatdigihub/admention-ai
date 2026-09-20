import pytest

from app.core.exceptions import InvalidYouTubeURLError
from app.services.youtube import YouTubeService
from app.utils.youtube import (
    extract_video_id,
    format_timestamp,
    parse_iso8601_duration,
    parse_published_at,
    timestamp_url,
    validate_youtube_url,
    generate_youtube_timestamp_url,
)

VALID_VIDEO_ID = "dQw4w9WgXcQ"


@pytest.mark.parametrize(
    ("url", "expected"),
    [
        (f"https://www.youtube.com/watch?v={VALID_VIDEO_ID}", VALID_VIDEO_ID),
        (f"https://youtu.be/{VALID_VIDEO_ID}", VALID_VIDEO_ID),
        (f"https://www.youtube.com/live/{VALID_VIDEO_ID}", VALID_VIDEO_ID),
        (f"https://www.youtube.com/watch?v={VALID_VIDEO_ID}&t=120", VALID_VIDEO_ID),
        (f"https://www.youtube.com/watch?v={VALID_VIDEO_ID}&feature=share", VALID_VIDEO_ID),
        (f"https://www.youtube.com/embed/{VALID_VIDEO_ID}", VALID_VIDEO_ID),
        (f"https://www.youtube.com/shorts/{VALID_VIDEO_ID}", VALID_VIDEO_ID),
        (f"https://m.youtube.com/watch?v={VALID_VIDEO_ID}&t=12s", VALID_VIDEO_ID),
        (f"youtu.be/{VALID_VIDEO_ID}", VALID_VIDEO_ID),
    ],
)
def test_extract_video_id_supports_common_formats(url: str, expected: str) -> None:
    assert extract_video_id(url) == expected
    assert validate_youtube_url(url) == expected


@pytest.mark.parametrize(
    "url",
    [
        "",
        "   ",
        "https://google.com",
        "https://example.com/video",
        "https://example.com/watch?v=dQw4w9WgXcQ",
        "https://www.youtube.com/watch?v=short",
        "https://www.youtube.com/feed/subscriptions",
        "not-a-url",
        "invalid string",
    ],
)
def test_extract_video_id_rejects_invalid_urls(url: str) -> None:
    with pytest.raises(InvalidYouTubeURLError):
        extract_video_id(url)


def test_youtube_service_normalizes_and_builds_timestamp_urls() -> None:
    service = YouTubeService()
    assert service.validate_url(f"https://youtu.be/{VALID_VIDEO_ID}") == VALID_VIDEO_ID
    assert service.extract_video_id(f"https://www.youtube.com/watch?v={VALID_VIDEO_ID}&t=120") == VALID_VIDEO_ID
    assert service.normalize_video_url(f"https://youtu.be/{VALID_VIDEO_ID}") == (
        f"https://www.youtube.com/watch?v={VALID_VIDEO_ID}"
    )
    assert service.generate_timestamp_url(VALID_VIDEO_ID, 872.4) == (
        f"https://www.youtube.com/watch?v={VALID_VIDEO_ID}&t=872s"
    )


def test_timestamp_helpers() -> None:
    assert timestamp_url(VALID_VIDEO_ID, 872.4) == f"https://www.youtube.com/watch?v={VALID_VIDEO_ID}&t=872s"
    assert generate_youtube_timestamp_url(VALID_VIDEO_ID, 0) == f"https://www.youtube.com/watch?v={VALID_VIDEO_ID}&t=0s"
    assert format_timestamp(872.4) == "00:14:32"
    assert format_timestamp(0) == "00:00:00"
    assert parse_iso8601_duration("PT1H2M3S") == 3723
    assert parse_iso8601_duration("PT15M") == 900
    assert parse_iso8601_duration("PT2H") == 7200
    published = parse_published_at("2026-09-20T10:00:00Z")
    assert published is not None
    assert published.year == 2026
    assert published.month == 9
    assert published.day == 20
