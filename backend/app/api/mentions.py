from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.mention import MentionSearchRequest, MentionSearchResponse
from app.services.mentions import MentionSearchService

router = APIRouter(prefix="/mentions", tags=["mentions"])


def get_mention_search_service(db: Session = Depends(get_db)) -> MentionSearchService:
    return MentionSearchService(db)


@router.post("/search", response_model=MentionSearchResponse)
def search_mentions(
    payload: MentionSearchRequest,
    service: MentionSearchService = Depends(get_mention_search_service),
) -> MentionSearchResponse:
    return service.search(
        payload.video_id,
        payload.advertiser,
        context_before=payload.context_before,
        context_after=payload.context_after,
    )
