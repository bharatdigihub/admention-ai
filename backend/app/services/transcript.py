import logging

from sqlalchemy.orm import Session

from app.core.exceptions import TranscriptUnavailableError, VideoNotFoundError
from app.models.transcript import TranscriptSegment
from app.models.video import Video
from app.providers.fixture_transcript import LocalFixtureTranscriptProvider
from app.providers.innertube_transcript import InnertubeTranscriptProvider
from app.providers.transcript import TranscriptCue, TranscriptProvider
from app.providers.whisper_transcript import WhisperTranscriptProvider
from app.providers.youtube_transcript import YouTubeTranscriptProvider
from app.providers.ytdlp_transcript import YtDlpTranscriptProvider
from app.repositories.transcript import TranscriptRepository
from app.repositories.video import VideoRepository
from app.schemas.transcript import TranscriptResponse, TranscriptSegmentResponse

logger = logging.getLogger(__name__)


class TranscriptService:
    """Retrieves, normalizes, and stores timestamped transcript segments."""

    def __init__(
        self,
        db: Session,
        providers: list[TranscriptProvider] | None = None,
    ) -> None:
        self.db = db
        self.videos = VideoRepository(db)
        self.segments = TranscriptRepository(db)
        self.providers = providers or [
            InnertubeTranscriptProvider(),
            YouTubeTranscriptProvider(),
            YtDlpTranscriptProvider(),
            LocalFixtureTranscriptProvider(),
            WhisperTranscriptProvider(),
        ]

    def normalize(self, cues: list[TranscriptCue]) -> list[TranscriptCue]:
        normalized: list[TranscriptCue] = []
        for cue in cues:
            text = " ".join((cue.text or "").replace("\n", " ").split())
            if not text:
                continue
            normalized.append(
                TranscriptCue(
                    start=max(0.0, float(cue.start)),
                    duration=max(0.0, float(cue.duration)),
                    text=text,
                )
            )
        return normalized

    def get_segments(self, youtube_video_id: str) -> list[TranscriptSegment]:
        video = self.videos.get_by_youtube_id(youtube_video_id)
        if video is None:
            return []
        return self.segments.list_for_video(video)

    def get_transcript(self, youtube_video_id: str) -> TranscriptResponse:
        video = self.videos.get_by_youtube_id(youtube_video_id)
        if video is None:
            raise VideoNotFoundError("Video was not found. Analyze the YouTube URL first.")

        if video.transcript_status == "pending" or not self.segments.list_for_video(video):
            if video.transcript_status not in {"available", "whisper", "fixture"}:
                try:
                    video = self.ensure_transcript(video)
                except TranscriptUnavailableError:
                    video = self.videos.get_by_youtube_id(youtube_video_id) or video

        segments = self.segments.list_for_video(video)
        return TranscriptResponse(
            video_id=video.youtube_video_id,
            transcript_status=video.transcript_status,
            segments=[
                TranscriptSegmentResponse(
                    start=segment.start_seconds,
                    duration=segment.duration_seconds,
                    text=segment.text,
                )
                for segment in segments
            ],
        )

    def ensure_transcript(self, video: Video, force: bool = False) -> Video:
        existing = self.segments.list_for_video(video)
        if existing and not force and video.transcript_status in {"available", "whisper", "fixture"}:
            logger.info("Skipping transcript fetch for %s; %s segments already stored", video.youtube_video_id, len(existing))
            return video

        last_error: Exception | None = None
        used_provider: TranscriptProvider | None = None
        cues: list[TranscriptCue] = []
        errors: list[str] = []

        for provider in self.providers:
            try:
                cues = self.normalize(provider.fetch(video.youtube_video_id))
                if not cues:
                    raise TranscriptUnavailableError("The transcript was empty.")
                used_provider = provider
                break
            except TranscriptUnavailableError as exc:
                logger.info("Transcript provider %s unavailable for %s: %s", provider.name, video.youtube_video_id, exc)
                last_error = exc
                errors.append(str(exc))
                continue
            except Exception as exc:
                logger.exception("Transcript provider %s failed for %s", provider.name, video.youtube_video_id)
                last_error = TranscriptUnavailableError(
                    "A timestamped transcript is not available for this video."
                )
                last_error.__cause__ = exc
                errors.append(f"{provider.name}: {exc}")
                continue

        if used_provider is None or not cues:
            video.transcript_status = "unavailable"
            self.db.commit()
            self.db.refresh(video)
            skip = ("Whisper fallback is disabled", "No local transcript fixture")
            meaningful = [item for item in errors if not any(token in item for token in skip)]
            message = "; ".join(meaningful[:3]) if meaningful else (str(last_error) if last_error else "")
            raise TranscriptUnavailableError(
                message or "A timestamped transcript is not available for this video."
            )

        self.segments.replace_for_video(video, cues)
        if used_provider.name == "whisper":
            video.transcript_status = "whisper"
        elif used_provider.name == "fixture":
            video.transcript_status = "fixture"
        else:
            video.transcript_status = "available"
        self.db.commit()
        self.db.refresh(video)
        logger.info(
            "Stored %s transcript segments for %s via %s",
            len(cues),
            video.youtube_video_id,
            used_provider.name,
        )
        return video
