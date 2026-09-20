import re

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.exceptions import AppError
from app.models.mention import Mention
from app.models.transcript import TranscriptSegment
from app.models.video import Video
from app.repositories.mention import MentionRepository
from app.repositories.video import VideoRepository
from app.schemas.mention import MentionItem, MentionSearchResponse
from app.services.advertiser import AdvertiserService
from app.utils.youtube import format_timestamp, generate_youtube_timestamp_url


class MentionSearchService:
    """Deterministic case-insensitive advertiser matching with alias support."""

    def __init__(self, db: Session) -> None:
        self.db = db
        self.videos = VideoRepository(db)
        self.mentions = MentionRepository(db)
        self.advertisers = AdvertiserService(db)
        settings = get_settings()
        self.context_before = max(0, settings.mention_context_before)
        self.context_after = max(0, settings.mention_context_after)

    def search(
        self,
        video_id: str,
        advertiser_name: str,
        context_before: int | None = None,
        context_after: int | None = None,
    ) -> MentionSearchResponse:
        video = self.videos.get_by_youtube_id(video_id)
        if video is None:
            raise AppError("Video not found. Analyze the YouTube URL first.", status_code=404)
        if video.transcript_status == "unavailable":
            raise AppError("A timestamped transcript is not available for this video.", status_code=422)
        if not video.transcript_segments:
            raise AppError("No transcript segments are stored for this video.", status_code=422)

        before = self.context_before if context_before is None else max(0, context_before)
        after = self.context_after if context_after is None else max(0, context_after)

        advertiser = self.advertisers.resolve(advertiser_name)
        terms = self.advertisers.search_terms(advertiser)
        pattern = self._build_pattern(terms)
        ordered = sorted(video.transcript_segments, key=lambda segment: (segment.start_seconds, segment.id))

        found: list[Mention] = []
        items: list[MentionItem] = []
        for index, segment in enumerate(ordered):
            match = pattern.search(segment.text)
            if match is None:
                continue
            matched_text = match.group(0)
            confidence = 1.0 if matched_text.lower() == advertiser.name.lower() else 0.9
            mention = Mention(
                video_id=video.id,
                advertiser_id=advertiser.id,
                transcript_segment_id=segment.id,
                timestamp_seconds=segment.start_seconds,
                matched_text=matched_text,
                mention_type="unknown",
                confidence=confidence,
            )
            found.append(mention)
            items.append(self._to_item(video, ordered, index, segment, matched_text, confidence, before, after))

        self.mentions.replace_for_search(video.id, advertiser.id, found)
        return MentionSearchResponse(
            advertiser=advertiser.name,
            total_mentions=len(items),
            mentions=items,
        )

    def _to_item(
        self,
        video: Video,
        ordered: list[TranscriptSegment],
        index: int,
        segment: TranscriptSegment,
        matched_text: str,
        confidence: float,
        context_before: int,
        context_after: int,
    ) -> MentionItem:
        previous = ordered[max(0, index - context_before) : index]
        following = ordered[index + 1 : index + 1 + context_after]
        return MentionItem(
            timestamp_seconds=segment.start_seconds,
            timestamp=format_timestamp(segment.start_seconds),
            text=segment.text,
            matched_text=matched_text,
            context_before=" ".join(item.text for item in previous),
            context_after=" ".join(item.text for item in following),
            mention_type="unknown",
            confidence=confidence,
            youtube_url=generate_youtube_timestamp_url(video.youtube_video_id, segment.start_seconds),
        )

    def _build_pattern(self, terms: list[str]) -> re.Pattern[str]:
        escaped = [re.escape(term) for term in terms if term]
        if not escaped:
            raise AppError("An advertiser name is required.")
        escaped.sort(key=len, reverse=True)
        return re.compile(r"(?<!\w)(?:" + "|".join(escaped) + r")(?!\w)", re.IGNORECASE)
