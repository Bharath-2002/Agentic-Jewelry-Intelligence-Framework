from fastapi import APIRouter
from app.api import scrape, jewels, status, filters

api_router = APIRouter()

api_router.include_router(scrape.router, tags=["scrape"])
api_router.include_router(status.router, tags=["status"])
api_router.include_router(jewels.router, tags=["jewels"])
api_router.include_router(filters.router, tags=["filters"])

__all__ = ["api_router"]
