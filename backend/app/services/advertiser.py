from __future__ import annotations

from sqlalchemy.orm import Session

from app.core.exceptions import AppError, ConflictError, NotFoundError
from app.models.advertiser import Advertiser, AdvertiserAlias
from app.repositories.advertiser import AdvertiserRepository
from app.schemas.advertiser import AdvertiserAliasResponse, AdvertiserResponse


def _clean_name(value: str) -> str:
    return " ".join((value or "").split())


class AdvertiserService:
    def __init__(self, db: Session) -> None:
        self.repository = AdvertiserRepository(db)

    def resolve(self, name: str) -> Advertiser:
        return self.repository.get_or_create(self._require_name(name))

    def search_terms(self, advertiser: Advertiser) -> list[str]:
        return self.repository.list_terms(advertiser)

    def list(self) -> list[AdvertiserResponse]:
        return [self.to_response(item) for item in self.repository.list_all()]

    def get(self, advertiser_id: int) -> AdvertiserResponse:
        return self.to_response(self._require(advertiser_id))

    def create(self, name: str, aliases: list[str] | None = None) -> AdvertiserResponse:
        cleaned = self._require_name(name)
        if self.repository.get_by_name(cleaned) is not None:
            raise ConflictError("An advertiser with that name already exists.")
        advertiser = self.repository.create(cleaned)
        for alias in aliases or []:
            self._add_alias(advertiser, alias)
        return self.to_response(self._require(advertiser.id))

    def update(self, advertiser_id: int, name: str) -> AdvertiserResponse:
        advertiser = self._require(advertiser_id)
        cleaned = self._require_name(name)
        conflict = self.repository.get_by_name(cleaned)
        if conflict is not None and conflict.id != advertiser.id:
            raise ConflictError("An advertiser with that name already exists.")
        return self.to_response(self.repository.update(advertiser, cleaned))

    def delete(self, advertiser_id: int) -> None:
        self.repository.delete(self._require(advertiser_id))

    def add_alias(self, advertiser_id: int, alias: str) -> AdvertiserResponse:
        advertiser = self._require(advertiser_id)
        self._add_alias(advertiser, alias)
        return self.to_response(self._require(advertiser.id))

    def delete_alias(self, advertiser_id: int, alias_id: int) -> AdvertiserResponse:
        self._require(advertiser_id)
        alias = self.repository.get_alias(advertiser_id, alias_id)
        if alias is None:
            raise NotFoundError("Alias was not found.")
        self.repository.delete_alias(alias)
        return self.to_response(self._require(advertiser_id))

    def _add_alias(self, advertiser: Advertiser, alias: str) -> AdvertiserAlias:
        cleaned = _clean_name(alias)
        if not cleaned:
            raise AppError("An alias is required.")
        if cleaned.lower() == advertiser.name.lower():
            raise ConflictError("Alias must be different from the advertiser name.")
        if self.repository.find_alias(advertiser.id, cleaned) is not None:
            raise ConflictError("That alias already exists for this advertiser.")
        return self.repository.add_alias(advertiser, cleaned)

    def _require(self, advertiser_id: int) -> Advertiser:
        advertiser = self.repository.get_by_id(advertiser_id)
        if advertiser is None:
            raise NotFoundError("Advertiser was not found.")
        return advertiser

    def _require_name(self, name: str) -> str:
        cleaned = _clean_name(name)
        if len(cleaned) < 2:
            raise AppError("An advertiser name is required.")
        return cleaned

    @staticmethod
    def to_response(advertiser: Advertiser) -> AdvertiserResponse:
        return AdvertiserResponse(
            id=advertiser.id,
            name=advertiser.name,
            aliases=[
                AdvertiserAliasResponse(id=item.id, alias=item.alias)
                for item in sorted(advertiser.aliases, key=lambda item: item.alias.lower())
            ],
        )
