from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.transcript import TranscriptResponse
from app.schemas.video import AnalyzeVideoRequest, AnalyzeVideoResponse
from app.services.transcript import TranscriptService
from app.services.video_analysis import VideoAnalysisService

router = APIRouter(prefix="/videos", tags=["videos"])


def get_video_analysis_service(db: Session = Depends(get_db)) -> VideoAnalysisService:
    return VideoAnalysisService(db)


def get_transcript_service(db: Session = Depends(get_db)) -> TranscriptService:
    return TranscriptService(db)


@router.post("/analyze", response_model=AnalyzeVideoResponse)
def analyze_video(
    payload: AnalyzeVideoRequest,
    service: VideoAnalysisService = Depends(get_video_analysis_service),
) -> AnalyzeVideoResponse:
    return service.analyze(payload.youtube_url)


@router.get("/{video_id}/transcript", response_model=TranscriptResponse)
def get_video_transcript(
    video_id: str,
    service: TranscriptService = Depends(get_transcript_service),
) -> TranscriptResponse:
    return service.get_transcript(video_id)
