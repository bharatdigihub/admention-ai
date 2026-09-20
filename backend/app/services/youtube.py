import logging

from sqlalchemy.orm import Session

from app.core.exceptions import DatabaseError
from app.models.video import Video
from app.providers.youtube_metadata import VideoMetadata, VideoMetadataProvider, YouTubeProvider
from app.repositories.video import VideoRepository
from app.schemas.video import AnalyzeVideoResponse
from app.utils.youtube import extract_video_id, normalize_watch_url, timestamp_url, validate_youtube_url

logger = logging.getLogger(__name__)


class YouTubeService:
    """Validates YouTube URLs, retrieves metadata, and persists video records."""

    def __init__(
        self,
        db: Session | None = None,
        metadata_provider: VideoMetadataProvider | None = None,
    ) -> None:
        self.repository = VideoRepository(db) if db is not None else None
        self.metadata_provider = metadata_provider or YouTubeProvider()

    def validate_url(self, youtube_url: str) -> str:
        return validate_youtube_url(youtube_url)

    def extract_video_id(self, youtube_url: str) -> str:
        return extract_video_id(youtube_url)

    def normalize_video_url(self, youtube_url: str) -> str:
        return normalize_watch_url(self.extract_video_id(youtube_url))

    def generate_timestamp_url(self, video_id: str, timestamp_seconds: float) -> str:
        return timestamp_url(video_id, timestamp_seconds)

    def get_video_metadata(self, youtube_url: str) -> VideoMetadata:
        video_id = self.validate_url(youtube_url)
        return self.metadata_provider.fetch(video_id)

    def analyze(self, youtube_url: str) -> AnalyzeVideoResponse:
        if self.repository is None:
            raise RuntimeError("YouTubeService requires a database session to analyze videos.")

        metadata = self.get_video_metadata(youtube_url)
        try:
            video = self.repository.upsert_from_metadata(metadata, transcript_status="pending")
        except DatabaseError:
            raise
        except Exception as exc:
            logger.exception("Unexpected error while storing video metadata for %s", metadata.video_id)
            raise DatabaseError() from exc
        return self.to_response(video)

    def normalize_url(self, youtube_url: str) -> str:
        return self.normalize_video_url(youtube_url)

    def get_metadata(self, youtube_url: str) -> VideoMetadata:
        return self.get_video_metadata(youtube_url)

    @staticmethod
    def to_response(video: Video) -> AnalyzeVideoResponse:
        return AnalyzeVideoResponse(
            video_id=video.youtube_video_id,
            title=video.title,
            channel=video.channel_name,
            published_at=video.published_at,
            duration_seconds=video.duration_seconds,
            thumbnail_url=video.thumbnail_url,
            transcript_status=video.transcript_status,
        )
