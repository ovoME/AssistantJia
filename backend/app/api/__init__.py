from fastapi import APIRouter
from app.api.health import router as health_router
from app.api.chat import router as chat_router
from app.api.books import router as books_router
from app.api.reader import router as reader_router
from app.api.recommend import router as recommend_router
from app.api.admin import router as admin_router

api_router = APIRouter()

api_router.include_router(health_router)
api_router.include_router(chat_router)
api_router.include_router(books_router)
api_router.include_router(reader_router)
api_router.include_router(recommend_router)
api_router.include_router(admin_router)

__all__ = ["api_router"]
