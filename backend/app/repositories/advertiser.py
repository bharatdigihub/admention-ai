from __future__ import annotations

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.advertiser import Advertiser, AdvertiserAlias


class AdvertiserRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def list_all(self) -> list[Advertiser]:
        return self.db.query(Advertiser).order_by(Advertiser.name.asc()).all()

    def get_by_id(self, advertiser_id: int) -> Advertiser | None:
        return self.db.get(Advertiser, advertiser_id)

    def get_by_name(self, name: str) -> Advertiser | None:
        return (
            self.db.query(Advertiser)
            .filter(func.lower(Advertiser.name) == name.lower())
            .one_or_none()
        )

    def get_or_create(self, name: str) -> Advertiser:
        advertiser = self.get_by_name(name)
        if advertiser is None:
            advertiser = Advertiser(name=name)
            self.db.add(advertiser)
            self.db.commit()
            self.db.refresh(advertiser)
        return advertiser

    def create(self, name: str) -> Advertiser:
        advertiser = Advertiser(name=name)
        self.db.add(advertiser)
        self.db.commit()
        self.db.refresh(advertiser)
        return advertiser

    def update(self, advertiser: Advertiser, name: str) -> Advertiser:
        advertiser.name = name
        self.db.commit()
        self.db.refresh(advertiser)
        return advertiser

    def delete(self, advertiser: Advertiser) -> None:
        self.db.delete(advertiser)
        self.db.commit()

    def list_terms(self, advertiser: Advertiser) -> list[str]:
        terms = [advertiser.name, *[alias.alias for alias in advertiser.aliases]]
        unique: list[str] = []
        seen: set[str] = set()
        for term in terms:
            key = term.strip().lower()
            if key and key not in seen:
                seen.add(key)
                unique.append(term.strip())
        return unique

    def get_alias(self, advertiser_id: int, alias_id: int) -> AdvertiserAlias | None:
        return (
            self.db.query(AdvertiserAlias)
            .filter(AdvertiserAlias.advertiser_id == advertiser_id, AdvertiserAlias.id == alias_id)
            .one_or_none()
        )

    def find_alias(self, advertiser_id: int, alias: str) -> AdvertiserAlias | None:
        return (
            self.db.query(AdvertiserAlias)
            .filter(
                AdvertiserAlias.advertiser_id == advertiser_id,
                func.lower(AdvertiserAlias.alias) == alias.lower(),
            )
            .one_or_none()
        )

    def add_alias(self, advertiser: Advertiser, alias: str) -> AdvertiserAlias:
        existing = self.find_alias(advertiser.id, alias)
        if existing:
            return existing
        record = AdvertiserAlias(advertiser_id=advertiser.id, alias=alias)
        self.db.add(record)
        self.db.commit()
        self.db.refresh(record)
        return record

    def delete_alias(self, alias: AdvertiserAlias) -> None:
        self.db.delete(alias)
        self.db.commit()
