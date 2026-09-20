from sqlalchemy.orm import Session

from app.models.transcript import TranscriptSegment
from app.models.video import Video
from app.providers.transcript import TranscriptCue


class TranscriptRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def list_for_video(self, video: Video) -> list[TranscriptSegment]:
        return (
            self.db.query(TranscriptSegment)
            .filter(TranscriptSegment.video_id == video.id)
            .order_by(TranscriptSegment.start_seconds.asc(), TranscriptSegment.id.asc())
            .all()
        )

    def replace_for_video(self, video: Video, cues: list[TranscriptCue]) -> list[TranscriptSegment]:
        self.db.query(TranscriptSegment).filter(TranscriptSegment.video_id == video.id).delete()
        segments: list[TranscriptSegment] = []
        for cue in cues:
            segment = TranscriptSegment(
                video_id=video.id,
                start_seconds=cue.start,
                duration_seconds=cue.duration,
                text=cue.text,
            )
            self.db.add(segment)
            segments.append(segment)
        self.db.commit()
        return self.list_for_video(video)
