from __future__ import annotations

from fastapi import APIRouter

from .cache import router as cache_router
from .chat import router as chat_router
from .gmail import router as gmail_router
from .meta import router as meta_router
from .context_optimization import router as context_optimization_router

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(meta_router)
api_router.include_router(chat_router)
api_router.include_router(gmail_router)
api_router.include_router(cache_router)
api_router.include_router(context_optimization_router)

__all__ = ["api_router"]
