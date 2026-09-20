from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.advertiser import (
    AdvertiserCreateRequest,
    AdvertiserResponse,
    AdvertiserUpdateRequest,
    AliasCreateRequest,
)
from app.services.advertiser import AdvertiserService

router = APIRouter(prefix="/advertisers", tags=["advertisers"])


def get_advertiser_service(db: Session = Depends(get_db)) -> AdvertiserService:
    return AdvertiserService(db)


@router.get("", response_model=list[AdvertiserResponse])
def list_advertisers(service: AdvertiserService = Depends(get_advertiser_service)) -> list[AdvertiserResponse]:
    return service.list()


@router.post("", response_model=AdvertiserResponse, status_code=status.HTTP_201_CREATED)
def create_advertiser(
    payload: AdvertiserCreateRequest,
    service: AdvertiserService = Depends(get_advertiser_service),
) -> AdvertiserResponse:
    return service.create(payload.name, payload.aliases)


@router.get("/{advertiser_id}", response_model=AdvertiserResponse)
def get_advertiser(
    advertiser_id: int,
    service: AdvertiserService = Depends(get_advertiser_service),
) -> AdvertiserResponse:
    return service.get(advertiser_id)


@router.put("/{advertiser_id}", response_model=AdvertiserResponse)
def update_advertiser(
    advertiser_id: int,
    payload: AdvertiserUpdateRequest,
    service: AdvertiserService = Depends(get_advertiser_service),
) -> AdvertiserResponse:
    return service.update(advertiser_id, payload.name)


@router.delete("/{advertiser_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_advertiser(
    advertiser_id: int,
    service: AdvertiserService = Depends(get_advertiser_service),
) -> Response:
    service.delete(advertiser_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/{advertiser_id}/aliases", response_model=AdvertiserResponse, status_code=status.HTTP_201_CREATED)
def add_advertiser_alias(
    advertiser_id: int,
    payload: AliasCreateRequest,
    service: AdvertiserService = Depends(get_advertiser_service),
) -> AdvertiserResponse:
    return service.add_alias(advertiser_id, payload.alias)


@router.delete("/{advertiser_id}/aliases/{alias_id}", response_model=AdvertiserResponse)
def delete_advertiser_alias(
    advertiser_id: int,
    alias_id: int,
    service: AdvertiserService = Depends(get_advertiser_service),
) -> AdvertiserResponse:
    return service.delete_alias(advertiser_id, alias_id)
