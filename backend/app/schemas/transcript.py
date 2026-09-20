from pydantic import BaseModel, Field


class TranscriptSegmentResponse(BaseModel):
    start: float
    duration: float
    text: str


class TranscriptResponse(BaseModel):
    video_id: str
    transcript_status: str
    segments: list[TranscriptSegmentResponse] = Field(default_factory=list)
