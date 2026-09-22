import logging
import os

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.exceptions import TranscriptUnavailableError, VideoNotFoundError
from app.models.transcript import TranscriptSegment
from app.models.video import Video
from app.providers.caption_mirror import CaptionMirrorTranscriptProvider
from app.providers.fixture_transcript import LocalFixtureTranscriptProvider
from app.providers.hostinger_proxy import HostingerCaptionProxyProvider
from app.providers.innertube_transcript import InnertubeTranscriptProvider
from app.providers.transcript import TranscriptCue, TranscriptProvider, is_youtube_ip_block
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
        self.providers = providers if providers is not None else default_transcript_providers()

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
            logger.info(
                "Skipping transcript fetch for %s; %s segments already stored",
                video.youtube_video_id,
                len(existing),
            )
            return video

        last_error: Exception | None = None
        used_provider: TranscriptProvider | None = None
        cues: list[TranscriptCue] = []
        # Collect (provider_name, exception_type, message) tuples for every failure.
        error_details: list[str] = []
        skip_direct_youtube = False

        for provider in self.providers:
            if skip_direct_youtube and getattr(provider, "direct_youtube", False):
                logger.info(
                    "Skipping transcript provider %s for %s after YouTube IP block",
                    provider.name,
                    video.youtube_video_id,
                )
                continue
            try:
                cues = self.normalize(provider.fetch(video.youtube_video_id))
                if not cues:
                    raise TranscriptUnavailableError("The transcript was empty.")
                used_provider = provider
                break
            except TranscriptUnavailableError as exc:
                # Log the real exception type so Render logs are actionable.
                logger.info(
                    "Transcript provider %s skipped for %s [%s]: %s",
                    provider.name,
                    video.youtube_video_id,
                    type(exc).__name__,
                    exc,
                )
                last_error = exc
                error_details.append(f"{provider.name}({type(exc).__name__}): {exc}")
                if getattr(provider, "direct_youtube", False) and is_youtube_ip_block(exc):
                    skip_direct_youtube = True
                continue
            except Exception as exc:
                # Unexpected failure — log the full traceback so we see the real cause.
                logger.exception(
                    "Transcript provider %s raised unexpected error for %s [%s]",
                    provider.name,
                    video.youtube_video_id,
                    type(exc).__name__,
                )
                wrapped = TranscriptUnavailableError(
                    f"{provider.name} failed unexpectedly: {type(exc).__name__}: {exc}"
                )
                wrapped.__cause__ = exc
                last_error = wrapped
                error_details.append(f"{provider.name}({type(exc).__name__}): {exc}")
                if getattr(provider, "direct_youtube", False) and is_youtube_ip_block(exc):
                    skip_direct_youtube = True
                continue

        if used_provider is None or not cues:
            video.transcript_status = "unavailable"
            self.db.commit()
            self.db.refresh(video)

            # Build a message that includes every provider's real failure reason.
            # Filter out noise-only messages (fixture/Whisper "not configured").
            noise_tokens = ("Whisper fallback is disabled", "No local transcript fixture")
            meaningful = [d for d in error_details if not any(t in d for t in noise_tokens)]
            summary = "; ".join(meaningful[:3]) if meaningful else (str(last_error) if last_error else "")

            logger.error(
                "All transcript providers exhausted for %s. Failures: %s",
                video.youtube_video_id,
                " | ".join(error_details) if error_details else "none",
            )

            raise TranscriptUnavailableError(
                summary or "A timestamped transcript is not available for this video."
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

    def ingest_cues(self, youtube_video_id: str, cues: list[TranscriptCue]) -> TranscriptResponse:
        video = self.videos.get_by_youtube_id(youtube_video_id)
        if video is None:
            raise VideoNotFoundError("Video was not found. Analyze the YouTube URL first.")

        normalized = self.normalize(cues)
        if not normalized:
            raise TranscriptUnavailableError("The uploaded transcript was empty.")

        self.segments.replace_for_video(video, normalized)
        video.transcript_status = "available"
        self.db.commit()
        self.db.refresh(video)
        logger.info(
            "Stored %s browser-recovered transcript segments for %s",
            len(normalized),
            video.youtube_video_id,
        )
        return self.get_transcript(youtube_video_id)


def default_transcript_providers() -> list[TranscriptProvider]:
    """Direct YouTube first locally; Hostinger PHP first on Render (blocked cloud IP)."""
    settings = get_settings()
    direct = [
        InnertubeTranscriptProvider(),
        YouTubeTranscriptProvider(),
        YtDlpTranscriptProvider(),
    ]
    hostinger = HostingerCaptionProxyProvider()
    mirrors = [CaptionMirrorTranscriptProvider()]
    tail = [
        LocalFixtureTranscriptProvider(),
        WhisperTranscriptProvider(),
    ]
    if prefer_hostinger_caption_proxy(settings):
        return [hostinger, *mirrors, *direct, *tail]
    return [*direct, hostinger, *mirrors, *tail]


def prefer_hostinger_caption_proxy(settings=None) -> bool:
    settings = settings or get_settings()
    on_render = bool(os.environ.get("RENDER")) or settings.app_env == "production"
    return (
        on_render
        and not settings.proxy_url
        and not settings.has_webshare
        and bool(settings.caption_proxy_url.strip())
    )
