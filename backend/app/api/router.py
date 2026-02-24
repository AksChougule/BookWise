from fastapi import APIRouter

from app.api.routes.books import router as books_router
from app.api.routes.curated import router as curated_router
from app.api.routes.generation import router as generation_router
from app.api.routes.health import router as health_router
from app.api.routes.search import router as search_router


api_router = APIRouter()
api_router.include_router(books_router, tags=["books"])
api_router.include_router(curated_router, tags=["curated"])
api_router.include_router(generation_router, tags=["generation"])
api_router.include_router(health_router, tags=["health"])
api_router.include_router(search_router, tags=["search"])
