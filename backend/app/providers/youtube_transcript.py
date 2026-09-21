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
            fetched = self._fetch_cues(video_id)
        except CouldNotRetrieveTranscript as exc:
            # Log the specific error class from youtube-transcript-api (e.g. IpAddressBlocked,
            # RequestBlocked, TooManyRequests) so Render logs show the real cause.
            logger.info(
                "YouTube captions unavailable for %s [%s]: %s",
                video_id,
                type(exc).__name__,
                exc,
            )
            raise TranscriptUnavailableError(
                f"youtube-transcript-api [{type(exc).__name__}]: {exc}"
            ) from exc
        except Exception as exc:
            logger.exception(
                "YouTube caption request failed for %s [%s]",
                video_id,
                type(exc).__name__,
            )
            raise TranscriptUnavailableError(
                f"youtube-transcript-api unexpected error [{type(exc).__name__}]: {exc}"
            ) from exc

        cues = [
            TranscriptCue(start=float(item.start), duration=float(item.duration), text=item.text)
            for item in fetched
        ]
        if not cues:
            raise TranscriptUnavailableError("The YouTube transcript was empty.")
        return cues

    def _fetch_cues(self, video_id: str):
        try:
            return self._api.fetch(video_id, languages=("en", "en-US", "en-GB", "en-orig"))
        except CouldNotRetrieveTranscript:
            if not hasattr(self._api, "list"):
                raise
            transcript_list = self._api.list(video_id)
            for transcript in transcript_list:
                try:
                    return transcript.fetch()
                except Exception:
                    continue
            raise


def get_youtube_transcript_provider() -> TranscriptProvider:
    return YouTubeTranscriptProvider()
