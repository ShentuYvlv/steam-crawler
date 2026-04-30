from fastapi import APIRouter

from app.api.routes.health import router as health_router
from app.api.routes.reply_drafts import router as reply_drafts_router
from app.api.routes.reply_records import router as reply_records_router
from app.api.routes.reply_strategies import router as reply_strategies_router
from app.api.routes.reviews import router as reviews_router
from app.api.routes.tasks import router as tasks_router

api_router = APIRouter()
api_router.include_router(health_router, tags=["health"])
api_router.include_router(reviews_router)
api_router.include_router(reply_drafts_router)
api_router.include_router(reply_records_router)
api_router.include_router(reply_strategies_router)
api_router.include_router(tasks_router)
