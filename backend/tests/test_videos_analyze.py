import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.exc import SQLAlchemyError

from app.api.videos import get_transcript_service, get_video_analysis_service
from app.core.exceptions import (
    DatabaseError,
    ExternalServiceError,
    TranscriptUnavailableError,
    VideoNotFoundError,
    YouTubeQuotaError,
    YouTubeTimeoutError,
)
from app.main import app
from app.models.video import Video
from app.providers.transcript import TranscriptCue
from app.providers.youtube_metadata import VideoMetadata, YouTubeProvider
from app.services.transcript import TranscriptService
from app.services.video_analysis import VideoAnalysisService

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

    def fetch(self, video_id: str) -> VideoMetadata:
        if isinstance(self._metadata, Exception):
            raise self._metadata
        assert video_id == self._metadata.video_id
        return self._metadata


class FakeTranscriptProvider:
    name = "youtube"

    def __init__(self, cues: list[TranscriptCue] | Exception) -> None:
        self._cues = cues

    def fetch(self, video_id: str) -> list[TranscriptCue]:
        if isinstance(self._cues, Exception):
            raise self._cues
        return list(self._cues)


def _override_analysis(
    db,
    metadata: VideoMetadata | Exception,
    transcript: list[TranscriptCue] | Exception | None = None,
) -> None:
    if transcript is None:
        transcript = TranscriptUnavailableError("A timestamped YouTube transcript is not available for this video.")
    provider = FakeTranscriptProvider(transcript)
    app.dependency_overrides[get_video_analysis_service] = lambda: VideoAnalysisService(
        db,
        metadata_provider=FakeMetadataProvider(metadata),
        transcript_providers=[provider],
    )
    app.dependency_overrides[get_transcript_service] = lambda: TranscriptService(db, providers=[provider])


def test_analyze_video_persists_metadata(client: TestClient, db) -> None:
    _override_analysis(db, SAMPLE_METADATA)

    response = client.post(
        "/api/videos/analyze",
        json={"youtube_url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["video_id"] == "dQw4w9WgXcQ"
    assert body["title"] == "Never Gonna Give You Up"
    assert body["channel"] == "Rick Astley"
    assert body["duration_seconds"] == 213
    assert body["thumbnail_url"] == SAMPLE_METADATA.thumbnail_url
    assert body["transcript_status"] == "unavailable"
    assert body["published_at"] is not None

    stored = db.query(Video).one()
    assert stored.youtube_video_id == "dQw4w9WgXcQ"
    assert stored.url == "https://www.youtube.com/watch?v=dQw4w9WgXcQ"


def test_analyze_video_stores_timestamped_transcript(client: TestClient, db) -> None:
    _override_analysis(
        db,
        SAMPLE_METADATA,
        [TranscriptCue(start=872.4, duration=4.2, text="Today's show is sponsored by Feldman Automotive")],
    )

    response = client.post(
        "/api/videos/analyze",
        json={"youtube_url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ"},
    )
    assert response.status_code == 200
    assert response.json()["transcript_status"] == "available"

    transcript = client.get("/api/videos/dQw4w9WgXcQ/transcript")
    assert transcript.status_code == 200
    body = transcript.json()
    assert body["video_id"] == "dQw4w9WgXcQ"
    assert body["transcript_status"] == "available"
    assert body["segments"] == [
        {
            "start": 872.4,
            "duration": 4.2,
            "text": "Today's show is sponsored by Feldman Automotive",
        }
    ]


def test_get_transcript_unknown_video(client: TestClient) -> None:
    response = client.get("/api/videos/dQw4w9WgXcQ/transcript")
    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()


def test_get_transcript_when_unavailable(client: TestClient, db) -> None:
    _override_analysis(db, SAMPLE_METADATA)
    client.post("/api/videos/analyze", json={"youtube_url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ"})

    response = client.get("/api/videos/dQw4w9WgXcQ/transcript")
    assert response.status_code == 200
    body = response.json()
    assert body["transcript_status"] == "unavailable"
    assert body["segments"] == []


def test_ingest_transcript_stores_browser_recovered_cues(client: TestClient, db) -> None:
    _override_analysis(db, SAMPLE_METADATA)
    client.post("/api/videos/analyze", json={"youtube_url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ"})

    response = client.post(
        "/api/videos/dQw4w9WgXcQ/transcript",
        json={
            "segments": [
                {"start": 43.12, "duration": 2.72, "text": "Never gonna give you up"},
            ]
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["transcript_status"] == "available"
    assert body["segments"][0]["text"] == "Never gonna give you up"

    stored = client.get("/api/videos/dQw4w9WgXcQ/transcript")
    assert stored.json()["transcript_status"] == "available"
    assert stored.json()["segments"][0]["start"] == 43.12


def test_analyze_video_rejects_invalid_url(client: TestClient) -> None:
    response = client.post("/api/videos/analyze", json={"youtube_url": "https://example.com/not-youtube"})
    assert response.status_code == 400
    assert "valid YouTube" in response.json()["detail"]


def test_analyze_video_rejects_empty_url(client: TestClient) -> None:
    response = client.post("/api/videos/analyze", json={"youtube_url": ""})
    assert response.status_code == 422


def test_analyze_video_handles_private_or_deleted(client: TestClient, db) -> None:
    _override_analysis(db, VideoNotFoundError("This video is private or unavailable."))

    response = client.post(
        "/api/videos/analyze",
        json={"youtube_url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ"},
    )
    assert response.status_code == 404
    assert "private" in response.json()["detail"]
    assert "Traceback" not in response.text


def test_analyze_video_handles_provider_failure(client: TestClient, db) -> None:
    _override_analysis(db, ExternalServiceError("YouTube rejected the metadata request."))

    response = client.post(
        "/api/videos/analyze",
        json={"youtube_url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ"},
    )
    assert response.status_code == 502
    assert response.json()["detail"] == "YouTube rejected the metadata request."


def test_analyze_video_handles_timeout(client: TestClient, db) -> None:
    _override_analysis(db, YouTubeTimeoutError())

    response = client.post(
        "/api/videos/analyze",
        json={"youtube_url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ"},
    )
    assert response.status_code == 504
    assert "too long" in response.json()["detail"]


def test_analyze_video_handles_quota_error(client: TestClient, db) -> None:
    _override_analysis(db, YouTubeQuotaError())

    response = client.post(
        "/api/videos/analyze",
        json={"youtube_url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ"},
    )
    assert response.status_code == 429
    assert "quota" in response.json()["detail"].lower()


def test_analyze_video_handles_database_failure(client: TestClient, db, monkeypatch) -> None:
    _override_analysis(db, SAMPLE_METADATA)

    def fail_commit() -> None:
        raise SQLAlchemyError("disk I/O error")

    monkeypatch.setattr(db, "commit", fail_commit)

    response = client.post(
        "/api/videos/analyze",
        json={"youtube_url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ"},
    )
    assert response.status_code == 500
    assert response.json()["detail"] == DatabaseError().message
    assert "Traceback" not in response.text
    assert "disk I/O" not in response.text


def test_oembed_provider_maps_http_errors() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, json={"error": "unauthorized"})

    transport = httpx.MockTransport(handler)
    client = httpx.Client(transport=transport)
    provider = YouTubeProvider(client=client, api_key="")

    with pytest.raises(VideoNotFoundError):
        provider.fetch("dQw4w9WgXcQ")


def test_oembed_provider_maps_deleted_video() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(404, json={"error": "not found"})

    provider = YouTubeProvider(client=httpx.Client(transport=httpx.MockTransport(handler)), api_key="")

    with pytest.raises(VideoNotFoundError):
        provider.fetch("dQw4w9WgXcQ")


def test_oembed_provider_maps_unknown_video_as_not_found() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(400, text="Bad Request")

    provider = YouTubeProvider(client=httpx.Client(transport=httpx.MockTransport(handler)), api_key="")

    with pytest.raises(VideoNotFoundError, match="not found"):
        provider.fetch("aaaaaaaaaaa")


def test_oembed_provider_maps_timeout() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.TimeoutException("timed out")

    provider = YouTubeProvider(client=httpx.Client(transport=httpx.MockTransport(handler)), api_key="")

    with pytest.raises(YouTubeTimeoutError):
        provider.fetch("dQw4w9WgXcQ")


def test_oembed_provider_maps_malformed_response() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text="not-json")

    provider = YouTubeProvider(client=httpx.Client(transport=httpx.MockTransport(handler)), api_key="")

    with pytest.raises(ExternalServiceError, match="unexpected"):
        provider.fetch("dQw4w9WgXcQ")


def test_oembed_provider_returns_real_shape_metadata() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "title": "Example Video",
                "author_name": "Woodward Sports",
                "thumbnail_url": "https://i.ytimg.com/vi/dQw4w9WgXcQ/hqdefault.jpg",
            },
        )

    provider = YouTubeProvider(client=httpx.Client(transport=httpx.MockTransport(handler)), api_key="")
    metadata = provider.fetch("dQw4w9WgXcQ")

    assert metadata.title == "Example Video"
    assert metadata.channel == "Woodward Sports"
    assert metadata.published_at is None
    assert metadata.duration_seconds is None


def test_data_api_quota_keeps_oembed_metadata() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if "oembed" in str(request.url):
            return httpx.Response(
                200,
                json={"title": "Example Video", "author_name": "Woodward Sports", "thumbnail_url": "https://img.example/t.jpg"},
            )
        return httpx.Response(
            403,
            json={"error": {"errors": [{"reason": "quotaExceeded"}], "message": "The request cannot be completed because you have exceeded your quota."}},
        )

    provider = YouTubeProvider(client=httpx.Client(transport=httpx.MockTransport(handler)), api_key="test-key")
    metadata = provider.fetch("dQw4w9WgXcQ")

    assert metadata.title == "Example Video"
    assert metadata.channel == "Woodward Sports"
    assert metadata.duration_seconds is None


def test_data_api_enriches_duration_and_published_at() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if "oembed" in str(request.url):
            return httpx.Response(
                200,
                json={"title": "Example Video", "author_name": "Woodward Sports", "thumbnail_url": "https://img.example/t.jpg"},
            )
        return httpx.Response(
            200,
            json={
                "items": [
                    {
                        "snippet": {
                            "title": "Example Video",
                            "channelTitle": "Woodward Sports",
                            "publishedAt": "2026-09-20T10:00:00Z",
                            "thumbnails": {"high": {"url": "https://img.example/high.jpg"}},
                        },
                        "contentDetails": {"duration": "PT2H"},
                        "status": {"privacyStatus": "public"},
                    }
                ]
            },
        )

    provider = YouTubeProvider(client=httpx.Client(transport=httpx.MockTransport(handler)), api_key="test-key")
    metadata = provider.fetch("dQw4w9WgXcQ")

    assert metadata.published_at == "2026-09-20T10:00:00Z"
    assert metadata.duration_seconds == 7200
    assert metadata.thumbnail_url == "https://img.example/high.jpg"
