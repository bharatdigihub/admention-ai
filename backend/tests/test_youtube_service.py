import pytest

from app.core.exceptions import ExternalServiceError, InvalidYouTubeURLError, VideoNotFoundError, YouTubeTimeoutError
from app.models.video import Video
from app.providers.youtube_metadata import VideoMetadata
from app.services.youtube import YouTubeService

SAMPLE_METADATA = VideoMetadata(
    video_id="dQw4w9WgXcQ",
    title="Never Gonna Give You Up",
    channel="Rick Astley",
    published_at="2009-10-25T06:57:33Z",
    duration_seconds=213,
    thumbnail_url="https://i.ytimg.com/vi/dQw4w9WgXcQ/hqdefault.jpg",
)


class FakeMetadataProvider:
    def __init__(self, metadata: VideoMetadata | Exception) -> None:
        self._metadata = metadata
        self.calls: list[str] = []

    def fetch(self, video_id: str) -> VideoMetadata:
        self.calls.append(video_id)
        if isinstance(self._metadata, Exception):
            raise self._metadata
        return self._metadata


def test_youtube_service_returns_metadata_for_valid_video() -> None:
    provider = FakeMetadataProvider(SAMPLE_METADATA)
    service = YouTubeService(metadata_provider=provider)

    metadata = service.get_video_metadata("https://www.youtube.com/watch?v=dQw4w9WgXcQ&feature=share")

    assert metadata.title == "Never Gonna Give You Up"
    assert metadata.channel == "Rick Astley"
    assert metadata.duration_seconds == 213
    assert provider.calls == ["dQw4w9WgXcQ"]


def test_youtube_service_rejects_invalid_video_url() -> None:
    service = YouTubeService(metadata_provider=FakeMetadataProvider(SAMPLE_METADATA))

    with pytest.raises(InvalidYouTubeURLError):
        service.get_video_metadata("https://google.com")


def test_youtube_service_surfaces_provider_error() -> None:
    service = YouTubeService(metadata_provider=FakeMetadataProvider(ExternalServiceError("YouTube rejected the metadata request.")))

    with pytest.raises(ExternalServiceError):
        service.get_video_metadata("https://www.youtube.com/watch?v=dQw4w9WgXcQ")


def test_youtube_service_surfaces_timeout() -> None:
    service = YouTubeService(metadata_provider=FakeMetadataProvider(YouTubeTimeoutError()))

    with pytest.raises(YouTubeTimeoutError):
        service.get_video_metadata("https://youtu.be/dQw4w9WgXcQ")


def test_youtube_service_surfaces_missing_video() -> None:
    service = YouTubeService(metadata_provider=FakeMetadataProvider(VideoNotFoundError()))

    with pytest.raises(VideoNotFoundError):
        service.get_video_metadata("https://www.youtube.com/watch?v=dQw4w9WgXcQ")


def test_analyze_upserts_video_with_pending_transcript(db) -> None:
    service = YouTubeService(db, metadata_provider=FakeMetadataProvider(SAMPLE_METADATA))

    response = service.analyze("https://www.youtube.com/live/dQw4w9WgXcQ")

    assert response.video_id == "dQw4w9WgXcQ"
    assert response.title == "Never Gonna Give You Up"
    assert response.channel == "Rick Astley"
    assert response.duration_seconds == 213
    assert response.transcript_status == "pending"

    stored = db.query(Video).filter(Video.youtube_video_id == "dQw4w9WgXcQ").one()
    assert stored.url == "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
    assert stored.channel_name == "Rick Astley"
    assert stored.transcript_status == "pending"
