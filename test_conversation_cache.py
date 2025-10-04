"""Tests for conversation caching functionality."""

import json
import tempfile
import time
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from server.services.conversation.cache import (
    ConversationCache,
    ConversationCacheEntry,
    get_conversation_cache,
    reset_conversation_cache,
)
from server.models.chat import ChatMessage


class TestConversationCacheEntry:
    """Test ConversationCacheEntry functionality."""
    
    def test_entry_creation(self):
        """Test cache entry creation."""
        messages = [
            ChatMessage(role="user", content="Hello"),
            ChatMessage(role="assistant", content="Hi there!"),
        ]
        
        entry = ConversationCacheEntry(
            conversation_id="test",
            messages=messages,
            size_bytes=100,
        )
        
        assert entry.conversation_id == "test"
        assert entry.messages == messages
        assert entry.size_bytes == 100
        assert entry.access_count == 0
        assert entry.last_accessed > 0


class TestConversationCache:
    """Test ConversationCache functionality."""
    
    def setup_method(self):
        """Set up test environment."""
        self.cache = ConversationCache(max_memory_mb=1, max_entries=5)
    
    def test_cache_initialization(self):
        """Test cache initialization."""
        assert self.cache.max_memory_bytes == 1024 * 1024  # 1MB
        assert self.cache.max_entries == 5
        assert len(self.cache._cache) == 0
        assert self.cache._current_memory_bytes == 0
    
    def test_add_to_cache(self):
        """Test adding conversations to cache."""
        messages = [
            ChatMessage(role="user", content="Hello"),
            ChatMessage(role="assistant", content="Hi there!"),
        ]
        
        # Mock the conversation log
        with patch.object(self.cache, '_load_from_disk', return_value=messages):
            cached_messages = self.cache.get_conversation("test")
        
        assert cached_messages == messages
        assert "test" in self.cache._cache
        assert self.cache._cache["test"].access_count == 1
    
    def test_cache_hit(self):
        """Test cache hit behavior."""
        messages = [
            ChatMessage(role="user", content="Hello"),
            ChatMessage(role="assistant", content="Hi there!"),
        ]
        
        # Mock the conversation log
        with patch.object(self.cache, '_load_from_disk', return_value=messages):
            # First call - cache miss
            cached_messages1 = self.cache.get_conversation("test")
            # Second call - cache hit
            cached_messages2 = self.cache.get_conversation("test")
        
        assert cached_messages1 == cached_messages2
        assert self.cache._cache["test"].access_count == 2
    
    def test_lru_eviction(self):
        """Test LRU eviction when max entries exceeded."""
        messages = [ChatMessage(role="user", content=f"Message {i}")]
        
        # Add more entries than max_entries
        with patch.object(self.cache, '_load_from_disk', return_value=messages):
            for i in range(7):  # More than max_entries (5)
                self.cache.get_conversation(f"conv_{i}")
        
        # Should only have max_entries
        assert len(self.cache._cache) == 5
        
        # Most recent entries should be present
        assert "conv_6" in self.cache._cache
        assert "conv_5" in self.cache._cache
        
        # Oldest entries should be evicted
        assert "conv_0" not in self.cache._cache
        assert "conv_1" not in self.cache._cache
    
    def test_memory_eviction(self):
        """Test memory-based eviction."""
        # Create a cache with very small memory limit
        small_cache = ConversationCache(max_memory_mb=0.001, max_entries=100)  # 1KB
        
        large_messages = [
            ChatMessage(role="user", content="x" * 1000)  # Large message
        ]
        
        with patch.object(small_cache, '_load_from_disk', return_value=large_messages):
            # First conversation should fit
            small_cache.get_conversation("conv_1")
            # Second conversation should trigger eviction
            small_cache.get_conversation("conv_2")
        
        # Should have evicted the first conversation
        assert "conv_1" not in small_cache._cache
        assert "conv_2" in small_cache._cache
    
    def test_invalidate_conversation(self):
        """Test conversation invalidation."""
        messages = [ChatMessage(role="user", content="Hello")]
        
        with patch.object(self.cache, '_load_from_disk', return_value=messages):
            self.cache.get_conversation("test")
        
        assert "test" in self.cache._cache
        
        self.cache.invalidate_conversation("test")
        assert "test" not in self.cache._cache
    
    def test_preload_conversation(self):
        """Test conversation preloading."""
        messages = [ChatMessage(role="user", content="Hello")]
        
        with patch.object(self.cache, '_load_from_disk', return_value=messages):
            self.cache.preload_conversation("test")
        
        assert "test" in self.cache._cache
        assert self.cache._cache["test"].access_count == 0  # Preloaded, not accessed
    
    def test_cache_stats(self):
        """Test cache statistics."""
        messages = [ChatMessage(role="user", content="Hello")]
        
        with patch.object(self.cache, '_load_from_disk', return_value=messages):
            self.cache.get_conversation("test1")
            self.cache.get_conversation("test2")
            self.cache.get_conversation("test1")  # Hit
        
        stats = self.cache.get_cache_stats()
        
        assert stats["entries_count"] == 2
        assert stats["memory_usage_mb"] > 0
        assert stats["memory_limit_mb"] == 1.0
        assert stats["total_accesses"] >= 3
        assert stats["avg_access_count"] > 0
    
    def test_calculate_messages_size(self):
        """Test message size calculation."""
        messages = [
            ChatMessage(role="user", content="Hello"),
            ChatMessage(role="assistant", content="Hi there!"),
        ]
        
        size = self.cache._calculate_messages_size(messages)
        assert size > 0
        
        # Should be larger than just the content length
        content_length = sum(len(msg.content) for msg in messages)
        assert size > content_length


class TestGlobalCacheFunctions:
    """Test global cache functions."""
    
    def setup_method(self):
        """Set up test environment."""
        reset_conversation_cache()
    
    def teardown_method(self):
        """Clean up test environment."""
        reset_conversation_cache()
    
    def test_get_conversation_cache_singleton(self):
        """Test that get_conversation_cache returns singleton."""
        cache1 = get_conversation_cache()
        cache2 = get_conversation_cache()
        
        assert cache1 is cache2
    
    def test_reset_conversation_cache(self):
        """Test cache reset functionality."""
        cache1 = get_conversation_cache()
        reset_conversation_cache()
        cache2 = get_conversation_cache()
        
        assert cache1 is not cache2


class TestCacheIntegration:
    """Test cache integration with conversation log."""
    
    def setup_method(self):
        """Set up test environment."""
        self.temp_dir = tempfile.mkdtemp()
        self.temp_path = Path(self.temp_dir) / "test_conversation.log"
        reset_conversation_cache()
    
    def teardown_method(self):
        """Clean up test environment."""
        reset_conversation_cache()
    
    def test_conversation_log_cache_integration(self):
        """Test that conversation log uses cache."""
        from server.services.conversation.log import ConversationLog
        
        # Create conversation log
        log = ConversationLog(self.temp_path)
        
        # Add some messages
        log.record_user_message("Hello")
        log.record_reply("Hi there!")
        
        # Get messages - should load from disk first time
        messages1 = log.to_chat_messages()
        assert len(messages1) == 2
        
        # Get messages again - should use cache
        messages2 = log.to_chat_messages()
        assert messages1 == messages2
        
        # Add new message - should invalidate cache
        log.record_user_message("How are you?")
        
        # Get messages - should reload from disk
        messages3 = log.to_chat_messages()
        assert len(messages3) == 3


class TestCachePerformance:
    """Test cache performance characteristics."""
    
    def setup_method(self):
        """Set up test environment."""
        self.cache = ConversationCache(max_memory_mb=10, max_entries=50)
    
    def test_cache_performance_improvement(self):
        """Test that cache provides performance improvement."""
        messages = [ChatMessage(role="user", content=f"Message {i}") for i in range(100)]
        
        with patch.object(self.cache, '_load_from_disk', return_value=messages) as mock_load:
            # First access - should call _load_from_disk
            start_time = time.time()
            cached_messages1 = self.cache.get_conversation("test")
            first_access_time = time.time() - start_time
            
            # Second access - should use cache
            start_time = time.time()
            cached_messages2 = self.cache.get_conversation("test")
            second_access_time = time.time() - start_time
        
        # Cache should be faster
        assert second_access_time < first_access_time
        assert cached_messages1 == cached_messages2
        
        # _load_from_disk should only be called once
        assert mock_load.call_count == 1
    
    def test_memory_efficiency(self):
        """Test that cache uses memory efficiently."""
        # Add multiple conversations
        for i in range(10):
            messages = [ChatMessage(role="user", content=f"Message {i}")]
            with patch.object(self.cache, '_load_from_disk', return_value=messages):
                self.cache.get_conversation(f"conv_{i}")
        
        stats = self.cache.get_cache_stats()
        
        # Should not exceed memory limit
        assert stats["memory_usage_percent"] <= 100.0
        assert stats["entries_count"] <= self.cache.max_entries


if __name__ == "__main__":
    pytest.main([__file__])
