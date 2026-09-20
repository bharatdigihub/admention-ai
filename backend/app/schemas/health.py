from pydantic import BaseModel


class HealthResponse(BaseModel):
    status: str
    caption_engine: str
