"""Cache monitoring endpoints for LLM optimization."""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Dict, Any

from ..services.conversation.cache import get_conversation_cache


router = APIRouter()


class CacheStatsResponse(BaseModel):
    """Cache statistics response."""
    entries_count: int
    memory_usage_mb: float
    memory_limit_mb: float
    memory_usage_percent: float
    total_accesses: int
    avg_access_count: float
    cache_hit_rate: float


@router.get("/cache/stats", response_model=CacheStatsResponse)
async def get_cache_stats() -> CacheStatsResponse:
    """Get conversation cache statistics."""
    try:
        cache = get_conversation_cache()
        stats = cache.get_cache_stats()
        
        return CacheStatsResponse(**stats)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to get cache stats: {str(exc)}")


@router.post("/cache/clear")
async def clear_cache() -> Dict[str, str]:
    """Clear conversation cache."""
    try:
        cache = get_conversation_cache()
        cache.invalidate_conversation("default")
        
        return {"message": "Cache cleared successfully"}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to clear cache: {str(exc)}")


@router.post("/cache/preload")
async def preload_cache() -> Dict[str, str]:
    """Preload conversation into cache."""
    try:
        cache = get_conversation_cache()
        cache.preload_conversation("default")
        
        return {"message": "Cache preloaded successfully"}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to preload cache: {str(exc)}")
