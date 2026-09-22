from pydantic import BaseModel, Field


class TranscriptSegmentResponse(BaseModel):
    start: float
    duration: float
    text: str


class TranscriptResponse(BaseModel):
    video_id: str
    transcript_status: str
    segments: list[TranscriptSegmentResponse] = Field(default_factory=list)


class TranscriptIngestRequest(BaseModel):
    segments: list[TranscriptSegmentResponse] = Field(..., min_length=1, max_length=20000)
