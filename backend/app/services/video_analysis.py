import logging

from sqlalchemy.orm import Session

from app.core.exceptions import TranscriptUnavailableError
from app.providers.transcript import TranscriptProvider
from app.providers.youtube_metadata import VideoMetadataProvider
from app.schemas.video import AnalyzeVideoResponse
from app.services.transcript import TranscriptService
from app.services.youtube import YouTubeService

logger = logging.getLogger(__name__)


class VideoAnalysisService:
    """Coordinates metadata retrieval and transcript ingestion."""

    def __init__(
        self,
        db: Session,
        metadata_provider: VideoMetadataProvider | None = None,
        transcript_providers: list[TranscriptProvider] | None = None,
    ) -> None:
        self.youtube = YouTubeService(db, metadata_provider=metadata_provider)
        self.transcript = TranscriptService(db, providers=transcript_providers)

    def analyze(self, youtube_url: str) -> AnalyzeVideoResponse:
        response = self.youtube.analyze(youtube_url)
        video = self.youtube.repository.get_by_youtube_id(response.video_id) if self.youtube.repository else None
        if video is None:
            return response

        try:
            video = self.transcript.ensure_transcript(video, force=False)
        except TranscriptUnavailableError:
            logger.info("No timestamped transcript available for %s", video.youtube_video_id)
            video.transcript_status = "unavailable"
            self.youtube.repository.db.commit()
            self.youtube.repository.db.refresh(video)

        return YouTubeService.to_response(video)
