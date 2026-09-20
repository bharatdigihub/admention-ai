from sqlalchemy.orm import Session

from app.models.mention import Mention


class MentionRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def replace_for_search(
        self,
        video_id: int,
        advertiser_id: int,
        mentions: list[Mention],
    ) -> list[Mention]:
        self.db.query(Mention).filter(
            Mention.video_id == video_id,
            Mention.advertiser_id == advertiser_id,
        ).delete()
        for mention in mentions:
            self.db.add(mention)
        self.db.commit()
        return (
            self.db.query(Mention)
            .filter(Mention.video_id == video_id, Mention.advertiser_id == advertiser_id)
            .order_by(Mention.timestamp_seconds.asc(), Mention.id.asc())
            .all()
        )
