from pydantic import BaseModel, Field


class MentionSearchRequest(BaseModel):
    video_id: str = Field(..., min_length=6)
    advertiser: str = Field(..., min_length=2)
    context_before: int | None = Field(default=None, ge=0, le=10)
    context_after: int | None = Field(default=None, ge=0, le=10)


class MentionItem(BaseModel):
    timestamp_seconds: float
    timestamp: str
    text: str
    matched_text: str
    context_before: str
    context_after: str
    mention_type: str
    confidence: float
    youtube_url: str


class MentionSearchResponse(BaseModel):
    advertiser: str
    total_mentions: int
    mentions: list[MentionItem]
