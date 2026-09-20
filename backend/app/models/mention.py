from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class Mention(Base):
    __tablename__ = "mentions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    video_id: Mapped[int] = mapped_column(ForeignKey("videos.id", ondelete="CASCADE"), index=True)
    advertiser_id: Mapped[int] = mapped_column(ForeignKey("advertisers.id", ondelete="CASCADE"), index=True)
    transcript_segment_id: Mapped[int | None] = mapped_column(
        ForeignKey("transcript_segments.id", ondelete="SET NULL"),
        nullable=True,
    )
    timestamp_seconds: Mapped[float] = mapped_column(Float)
    matched_text: Mapped[str] = mapped_column(Text)
    mention_type: Mapped[str] = mapped_column(String(50), default="unknown")
    confidence: Mapped[float] = mapped_column(Float, default=1.0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    video = relationship("Video", back_populates="mentions")
    advertiser = relationship("Advertiser", back_populates="mentions")
    transcript_segment = relationship("TranscriptSegment", back_populates="mentions")
