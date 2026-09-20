import logging

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.exceptions import DatabaseError
from app.models.video import Video
from app.providers.youtube_metadata import VideoMetadata
from app.utils.youtube import normalize_watch_url, parse_published_at

logger = logging.getLogger(__name__)


class VideoRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get_by_youtube_id(self, youtube_video_id: str) -> Video | None:
        return self.db.query(Video).filter(Video.youtube_video_id == youtube_video_id).one_or_none()

    def get_by_id(self, video_id: int) -> Video | None:
        return self.db.get(Video, video_id)

    def upsert_from_metadata(self, metadata: VideoMetadata, transcript_status: str = "pending") -> Video:
        try:
            video = self.get_by_youtube_id(metadata.video_id)
            if video is None:
                video = Video(youtube_video_id=metadata.video_id)
                self.db.add(video)

            video.url = normalize_watch_url(metadata.video_id)
            video.title = metadata.title
            video.channel_name = metadata.channel
            video.published_at = parse_published_at(metadata.published_at)
            video.duration_seconds = metadata.duration_seconds
            video.thumbnail_url = metadata.thumbnail_url
            video.transcript_status = transcript_status
            self.db.commit()
            self.db.refresh(video)
            return video
        except DatabaseError:
            raise
        except SQLAlchemyError as exc:
            logger.exception("Database error while saving video %s", metadata.video_id)
            self.db.rollback()
            raise DatabaseError() from exc
