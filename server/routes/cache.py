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
        cache.clear()
        
        return {"message": "Cache cleared successfully"}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to clear cache: {str(exc)}")


@router.post("/cache/preload")
async def preload_cache() -> Dict[str, str]:
    """Preload conversation into cache."""
    try:
        cache = get_conversation_cache()
        from ..services.conversation.log import get_conversation_log
        conversation_log = get_conversation_log()
        messages = conversation_log.to_chat_messages()
        cache.set_conversation("default", messages)
        
        return {"message": "Cache preloaded successfully"}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to preload cache: {str(exc)}")


@router.get("/cache/inspect")
async def inspect_cache() -> Dict[str, Any]:
    """Inspect detailed cache contents and data."""
    try:
        cache = get_conversation_cache()
        stats = cache.get_cache_stats()
        
        # Get cached conversation data
        cached_messages = cache.get_conversation("default")
        
        return {
            "cache_stats": stats,
            "cached_conversation": {
                "conversation_id": "default",
                "message_count": len(cached_messages) if cached_messages else 0,
                "sample_messages": [
                    {
                        "role": msg.role,
                        "content": msg.content[:100] + "..." if len(msg.content) > 100 else msg.content,
                        "timestamp": msg.timestamp
                    }
                    for msg in (cached_messages[:3] if cached_messages else [])
                ],
                "total_content_length": sum(len(msg.content) for msg in cached_messages) if cached_messages else 0,
                "message_types": {
                    "user": len([m for m in cached_messages if m.role == "user"]) if cached_messages else 0,
                    "assistant": len([m for m in cached_messages if m.role == "assistant"]) if cached_messages else 0
                }
            }
        }
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to inspect cache: {str(exc)}")
