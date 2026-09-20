from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class Advertiser(Base):
    __tablename__ = "advertisers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )

    aliases = relationship("AdvertiserAlias", back_populates="advertiser", cascade="all, delete-orphan")
    mentions = relationship("Mention", back_populates="advertiser")


class AdvertiserAlias(Base):
    __tablename__ = "advertiser_aliases"
    __table_args__ = (
        UniqueConstraint("advertiser_id", "alias", name="uq_advertiser_aliases_advertiser_alias"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    advertiser_id: Mapped[int] = mapped_column(ForeignKey("advertisers.id", ondelete="CASCADE"), index=True)
    alias: Mapped[str] = mapped_column(String(255), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    advertiser = relationship("Advertiser", back_populates="aliases")
