from datetime import datetime

from pydantic import BaseModel, Field


class AnalyzeVideoRequest(BaseModel):
    youtube_url: str = Field(..., min_length=8)


class AnalyzeVideoResponse(BaseModel):
    video_id: str
    title: str | None
    channel: str | None
    published_at: datetime | None
    duration_seconds: int | None
    thumbnail_url: str | None
    transcript_status: str
    transcript_error: str | None = None
