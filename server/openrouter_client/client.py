from __future__ import annotations

import hashlib
import json
import threading
import time
from typing import Any, Dict, List, Optional

import httpx

from ..config import get_settings
from ..services.conversation.hybrid_cache_strategy import get_hybrid_cache_strategy, CacheDecision
from ..logging_config import logger

OpenRouterBaseURL = "https://openrouter.ai/api/v1"


class OpenRouterError(RuntimeError):
    """Raised when the OpenRouter API returns an error response."""


def _headers(*, api_key: Optional[str] = None) -> Dict[str, str]:
    settings = get_settings()
    key = (api_key or settings.openrouter_api_key or "").strip()
    if not key:
        raise OpenRouterError("Missing OpenRouter API key")

    headers = {
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }

    return headers


def _build_messages(messages: List[Dict[str, str]], system: Optional[str]) -> List[Dict[str, str]]:
    if system:
        return [{"role": "system", "content": system}, *messages]
    return messages


def _handle_response_error(exc: httpx.HTTPStatusError) -> None:
    response = exc.response
    detail: str
    try:
        payload = response.json()
        detail = payload.get("error") or payload.get("message") or json.dumps(payload)
    except Exception:
        detail = response.text
    raise OpenRouterError(f"OpenRouter request failed ({response.status_code}): {detail}") from exc


async def request_chat_completion(
    *,
    model: str,
    messages: List[Dict[str, str]],
    system: Optional[str] = None,
    api_key: Optional[str] = None,
    tools: Optional[List[Dict[str, Any]]] = None,
    base_url: str = OpenRouterBaseURL,
) -> Dict[str, Any]:
    """Request a chat completion and return the raw JSON payload."""

    # Build request data for cache analysis
    request_data = {
        "model": model,
        "messages": messages,
        "system": system,
        "tools": tools,
    }
    
    # Generate cache key
    cache_key = _generate_cache_key(request_data)
    
    # Get hybrid cache strategy
    cache_strategy = get_hybrid_cache_strategy()
    
    # Determine cache policy
    cache_policy = cache_strategy.determine_cache_policy(request_data)
    
    # Check cache based on policy
    if cache_policy.decision != CacheDecision.DONT_CACHE:
        cached_response = _get_cached_response(cache_key)
        if cached_response is not None:
            logger.debug(
                "response cache hit",
                extra={
                    "cache_key": cache_key[:16] + "...",
                    "policy": cache_policy.decision.value,
                    "confidence": cache_policy.confidence,
                }
            )
            return cached_response

    # Make API call
    payload: Dict[str, object] = {
        "model": model,
        "messages": _build_messages(messages, system),
        "stream": False,
    }
    if tools:
        payload["tools"] = tools

    url = f"{base_url.rstrip('/')}/chat/completions"

    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(
                url,
                headers=_headers(api_key=api_key),
                json=payload,
                timeout=60.0,
            )
            try:
                response.raise_for_status()
            except httpx.HTTPStatusError as exc:
                _handle_response_error(exc)
            
            response_data = response.json()
            
            # Cache response based on policy
            if cache_policy.decision != CacheDecision.DONT_CACHE:
                _cache_response(cache_key, response_data, cache_policy)
            
            return response_data
        except httpx.HTTPStatusError as exc:
            _handle_response_error(exc)
        except httpx.HTTPError as exc:
            raise OpenRouterError(f"OpenRouter request failed: {exc}") from exc

    raise OpenRouterError("OpenRouter request failed: unknown error")


# Simple in-memory cache for responses
_response_cache: Dict[str, Dict[str, Any]] = {}
_cache_timestamps: Dict[str, float] = {}
_cache_lock = threading.RLock()


def _generate_cache_key(request_data: Dict[str, Any]) -> str:
    """Generate a cache key for the request."""
    # Create a deterministic representation
    request_json = json.dumps(request_data, sort_keys=True)
    return hashlib.sha256(request_json.encode('utf-8')).hexdigest()


def _get_cached_response(cache_key: str) -> Optional[Dict[str, Any]]:
    """Get cached response if available and not expired."""
    with _cache_lock:
        if cache_key in _response_cache:
            # Check if expired (simple TTL check)
            timestamp = _cache_timestamps.get(cache_key, 0)
            if time.time() - timestamp < 3600:  # 1 hour default TTL
                return _response_cache[cache_key]
            else:
                # Remove expired entry
                _response_cache.pop(cache_key, None)
                _cache_timestamps.pop(cache_key, None)
        return None


def _cache_response(cache_key: str, response: Dict[str, Any], cache_policy) -> None:
    """Cache response based on policy."""
    with _cache_lock:
        _response_cache[cache_key] = response
        _cache_timestamps[cache_key] = time.time()
        
        logger.debug(
            "response cached",
            extra={
                "cache_key": cache_key[:16] + "...",
                "policy": cache_policy.decision.value,
                "ttl_seconds": cache_policy.ttl_seconds,
            }
        )


def clear_response_cache() -> None:
    """Clear all cached responses."""
    with _cache_lock:
        _response_cache.clear()
        _cache_timestamps.clear()
        logger.info("response cache cleared")


def get_cache_stats() -> Dict[str, Any]:
    """Get cache statistics."""
    with _cache_lock:
        current_time = time.time()
        active_entries = 0
        
        # Count non-expired entries
        for cache_key in _response_cache:
            timestamp = _cache_timestamps.get(cache_key, 0)
            if current_time - timestamp < 3600:  # 1 hour TTL
                active_entries += 1
        
        return {
            "total_entries": len(_response_cache),
            "active_entries": active_entries,
            "expired_entries": len(_response_cache) - active_entries,
        }


__all__ = ["OpenRouterError", "request_chat_completion", "OpenRouterBaseURL", "clear_response_cache", "get_cache_stats"]
