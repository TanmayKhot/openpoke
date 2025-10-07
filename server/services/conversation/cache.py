"""Intelligent conversation caching for LLM performance optimization."""

from __future__ import annotations

import json
import threading
import time
from collections import OrderedDict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from ...logging_config import logger
from .log import ConversationLog, get_conversation_log
from ..conversation.chat_handler import ChatMessage


@dataclass
class ConversationCacheEntry:
    """Single conversation cache entry."""
    
    conversation_id: str
    messages: List[ChatMessage]
    last_accessed: float = field(default_factory=time.time)
    access_count: int = 0
    size_bytes: int = 0


class ConversationCache:
    """LRU cache for conversation data to optimize LLM performance."""
    
    def __init__(self, max_memory_mb: int = 512, max_entries: int = 100):
        """
        Initialize conversation cache.
        
        Args:
            max_memory_mb: Maximum memory usage in MB
            max_entries: Maximum number of conversations to cache
        """
        self.max_memory_bytes = max_memory_mb * 1024 * 1024
        self.max_entries = max_entries
        self._cache: OrderedDict[str, ConversationCacheEntry] = OrderedDict()
        self._lock = threading.RLock()
        self._current_memory_bytes = 0
        self._conversation_log = get_conversation_log()
        
        logger.info(
            "conversation cache initialized",
            extra={
                "max_memory_mb": max_memory_mb,
                "max_entries": max_entries,
            }
        )
    
    def get_conversation(self, conversation_id: str = "default") -> List[ChatMessage]:
        """
        Get conversation messages, loading from cache or disk as needed.
        
        Args:
            conversation_id: ID of conversation to retrieve
            
        Returns:
            List of chat messages
        """
        with self._lock:
            # Check cache first
            if conversation_id in self._cache:
                entry = self._cache[conversation_id]
                entry.last_accessed = time.time()
                entry.access_count += 1
                
                # Move to end (most recently used)
                self._cache.move_to_end(conversation_id)
                
                # Only log cache hits for user-initiated requests, not background processes
                if entry.access_count <= 5:  # First few accesses are likely user-initiated
                    logger.info(
                        "🎯 CONVERSATION CACHE HIT",
                        extra={
                            "conversation_id": conversation_id,
                            "access_count": entry.access_count,
                            "cached_messages": len(entry.messages),
                            "cache_size_mb": round(self._current_memory_bytes / (1024 * 1024), 2),
                            "cache_entries": len(self._cache),
                        }
                    )
                else:
                    # Log debug level for frequent background access
                    logger.debug(
                        "🎯 CONVERSATION CACHE HIT (background)",
                        extra={
                            "conversation_id": conversation_id,
                            "access_count": entry.access_count,
                            "cached_messages": len(entry.messages),
                        }
                    )
                
                return entry.messages
            
            # Cache miss - load from disk
            logger.info(
                "❌ CONVERSATION CACHE MISS",
                extra={
                    "conversation_id": conversation_id,
                    "cache_size_mb": round(self._current_memory_bytes / (1024 * 1024), 2),
                    "cache_entries": len(self._cache),
                }
            )
            
            messages = self._load_from_disk(conversation_id)
            self._add_to_cache(conversation_id, messages)
            
            return messages
    
    def preload_conversation(self, conversation_id: str = "default") -> None:
        """
        Preload a conversation into cache.
        
        Args:
            conversation_id: ID of conversation to preload
        """
        with self._lock:
            if conversation_id not in self._cache:
                messages = self._load_from_disk(conversation_id)
                self._add_to_cache(conversation_id, messages)
                
                logger.info(
                    "🔄 CONVERSATION PRELOADED",
                    extra={
                        "conversation_id": conversation_id,
                        "messages_count": len(messages),
                        "cache_entries": len(self._cache),
                        "total_cache_mb": round(self._current_memory_bytes / (1024 * 1024), 2),
                    }
                )
    
    def invalidate_conversation(self, conversation_id: str = "default") -> None:
        """
        Remove conversation from cache.
        
        Args:
            conversation_id: ID of conversation to invalidate
        """
        with self._lock:
            if conversation_id in self._cache:
                entry = self._cache.pop(conversation_id)
                self._current_memory_bytes -= entry.size_bytes
                
                logger.info(
                    "🗑️ CONVERSATION CACHE INVALIDATED",
                    extra={
                        "conversation_id": conversation_id,
                        "freed_mb": round(entry.size_bytes / (1024 * 1024), 2),
                        "remaining_cache_mb": round(self._current_memory_bytes / (1024 * 1024), 2),
                        "remaining_entries": len(self._cache),
                    }
                )
    
    def clear(self) -> None:
        """Clear all cached conversations."""
        with self._lock:
            entries_cleared = len(self._cache)
            memory_freed = self._current_memory_bytes
            
            self._cache.clear()
            self._current_memory_bytes = 0
            
            logger.info(
                "🗑️ CONVERSATION CACHE CLEARED",
                extra={
                    "entries_cleared": entries_cleared,
                    "memory_freed_mb": round(memory_freed / (1024 * 1024), 2),
                }
            )
    
    def get_cache_stats(self) -> Dict[str, any]:
        """Get cache statistics."""
        with self._lock:
            total_accesses = sum(entry.access_count for entry in self._cache.values())
            avg_access_count = total_accesses / len(self._cache) if self._cache else 0
            
            return {
                "entries_count": len(self._cache),
                "memory_usage_mb": self._current_memory_bytes / (1024 * 1024),
                "memory_limit_mb": self.max_memory_bytes / (1024 * 1024),
                "memory_usage_percent": (self._current_memory_bytes / self.max_memory_bytes) * 100,
                "total_accesses": total_accesses,
                "avg_access_count": avg_access_count,
                "cache_hit_rate": self._calculate_hit_rate(),
            }
    
    def _load_from_disk(self, conversation_id: str) -> List[ChatMessage]:
        """Load conversation from disk."""
        try:
            # For now, we only support the default conversation
            # This can be extended to support multiple conversations
            if conversation_id == "default":
                return self._conversation_log.to_chat_messages()
            else:
                logger.warning(
                    "unsupported conversation ID",
                    extra={"conversation_id": conversation_id}
                )
                return []
        except Exception as exc:
            logger.error(
                "failed to load conversation from disk",
                extra={
                    "conversation_id": conversation_id,
                    "error": str(exc),
                }
            )
            return []
    
    def _add_to_cache(self, conversation_id: str, messages: List[ChatMessage]) -> None:
        """Add conversation to cache with LRU eviction."""
        # Calculate size
        size_bytes = self._calculate_messages_size(messages)
        
        # Create cache entry
        entry = ConversationCacheEntry(
            conversation_id=conversation_id,
            messages=messages,
            size_bytes=size_bytes,
        )
        
        # Check if we need to evict entries
        while (self._current_memory_bytes + size_bytes > self.max_memory_bytes or 
               len(self._cache) >= self.max_entries):
            if not self._cache:
                break
            
            # Remove least recently used entry
            oldest_id, oldest_entry = self._cache.popitem(last=False)
            self._current_memory_bytes -= oldest_entry.size_bytes
            
            logger.info(
                "🗑️ CONVERSATION CACHE EVICTED",
                extra={
                    "evicted_id": oldest_id,
                    "evicted_size_mb": round(oldest_entry.size_bytes / (1024 * 1024), 2),
                    "evicted_access_count": oldest_entry.access_count,
                    "remaining_cache_mb": round(self._current_memory_bytes / (1024 * 1024), 2),
                }
            )
        
        # Add new entry
        self._cache[conversation_id] = entry
        self._current_memory_bytes += size_bytes
        
        logger.info(
            "📥 CONVERSATION ADDED TO CACHE",
            extra={
                "conversation_id": conversation_id,
                "messages_count": len(messages),
                "size_mb": round(size_bytes / (1024 * 1024), 2),
                "cache_entries": len(self._cache),
                "total_cache_mb": round(self._current_memory_bytes / (1024 * 1024), 2),
                "memory_usage_percent": round((self._current_memory_bytes / self.max_memory_bytes) * 100, 1),
            }
        )
    
    def _calculate_messages_size(self, messages: List[ChatMessage]) -> int:
        """Calculate approximate memory size of messages."""
        try:
            # Serialize to JSON to get accurate size
            serialized = json.dumps([msg.dict() for msg in messages])
            return len(serialized.encode('utf-8'))
        except Exception:
            # Fallback: rough estimate
            return sum(len(msg.content) * 2 for msg in messages)  # Rough estimate
    
    def _calculate_hit_rate(self) -> float:
        """Calculate cache hit rate."""
        if not self._cache:
            return 0.0
        
        total_accesses = sum(entry.access_count for entry in self._cache.values())
        if total_accesses == 0:
            return 0.0
        
        # This is a simplified calculation - in a real implementation,
        # we'd track total requests vs cache hits
        return min(100.0, (total_accesses / len(self._cache)) * 10)


# Global cache instance
_conversation_cache: Optional[ConversationCache] = None
_cache_lock = threading.Lock()


def get_conversation_cache() -> ConversationCache:
    """Get global conversation cache instance."""
    global _conversation_cache
    if _conversation_cache is None:
        with _cache_lock:
            if _conversation_cache is None:
                from ...config import get_settings
                settings = get_settings()
                _conversation_cache = ConversationCache(
                    max_memory_mb=settings.conversation_cache_mb,
                    max_entries=settings.conversation_cache_max_entries
                )
    return _conversation_cache


def reset_conversation_cache() -> None:
    """Reset global conversation cache (for testing)."""
    global _conversation_cache
    with _cache_lock:
        _conversation_cache = None


__all__ = ["ConversationCache", "get_conversation_cache", "reset_conversation_cache"]
