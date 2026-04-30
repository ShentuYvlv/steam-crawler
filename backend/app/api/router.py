from fastapi import APIRouter

from app.api.routes.health import router as health_router
from app.api.routes.reply_strategies import router as reply_strategies_router
from app.api.routes.reviews import router as reviews_router

api_router = APIRouter()
api_router.include_router(health_router, tags=["health"])
api_router.include_router(reviews_router)
api_router.include_router(reply_strategies_router)
