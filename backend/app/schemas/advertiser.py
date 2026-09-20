from pydantic import BaseModel, Field


class AdvertiserAliasResponse(BaseModel):
    id: int
    alias: str


class AdvertiserResponse(BaseModel):
    id: int
    name: str
    aliases: list[AdvertiserAliasResponse] = Field(default_factory=list)


class AdvertiserCreateRequest(BaseModel):
    name: str = Field(..., min_length=2, max_length=255)
    aliases: list[str] = Field(default_factory=list)


class AdvertiserUpdateRequest(BaseModel):
    name: str = Field(..., min_length=2, max_length=255)


class AliasCreateRequest(BaseModel):
    alias: str = Field(..., min_length=1, max_length=255)
