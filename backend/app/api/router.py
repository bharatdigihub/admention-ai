from fastapi import APIRouter

from app.api import advertisers, health, mentions, videos

api_router = APIRouter(prefix="/api")
api_router.include_router(health.router)
api_router.include_router(videos.router)
api_router.include_router(advertisers.router)
api_router.include_router(mentions.router)
