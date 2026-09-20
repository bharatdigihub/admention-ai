import logging

from youtube_transcript_api import YouTubeTranscriptApi
from youtube_transcript_api._errors import CouldNotRetrieveTranscript

from app.core.exceptions import TranscriptUnavailableError
from app.providers.transcript import TranscriptCue, TranscriptProvider

logger = logging.getLogger(__name__)


class YouTubeTranscriptProvider:
    """Retrieves timestamped captions from YouTube when they exist."""

    name = "youtube"

    def __init__(self, api: YouTubeTranscriptApi | None = None) -> None:
        self._api = api or YouTubeTranscriptApi()

    def fetch(self, video_id: str) -> list[TranscriptCue]:
        try:
            fetched = self._api.fetch(video_id, languages=("en", "en-US", "en-GB"))
        except CouldNotRetrieveTranscript as exc:
            logger.info("YouTube captions unavailable for %s: %s", video_id, exc)
            raise TranscriptUnavailableError(
                "A timestamped YouTube transcript is not available for this video."
            ) from exc
        except Exception as exc:
            logger.exception("YouTube caption request failed for %s", video_id)
            raise TranscriptUnavailableError(
                "A timestamped YouTube transcript is not available for this video."
            ) from exc

        cues = [
            TranscriptCue(start=float(item.start), duration=float(item.duration), text=item.text)
            for item in fetched
        ]
        if not cues:
            raise TranscriptUnavailableError("The YouTube transcript was empty.")
        return cues


def get_youtube_transcript_provider() -> TranscriptProvider:
    return YouTubeTranscriptProvider()
