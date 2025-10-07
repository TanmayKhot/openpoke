"""Unit tests for context optimization service."""

import pytest
import time
from unittest.mock import Mock, patch
from typing import List

from server.services.conversation.context_optimizer import (
    ContextOptimizer,
    ContextOptimizationResult,
    ContextSegment,
    ContextRelevanceLevel,
    get_context_optimizer,
    reset_context_optimizer,
)
from server.models import ChatMessage


class TestContextOptimizer:
    """Test cases for ContextOptimizer class."""

    def setup_method(self):
        """Set up test fixtures."""
        # Reset global optimizer for clean tests
        reset_context_optimizer()
        
        # Mock settings
        self.mock_settings = Mock()
        self.mock_settings.context_optimization_enabled = True
        self.mock_settings.context_max_tokens = 8000
        self.mock_settings.context_recent_messages_count = 10
        self.mock_settings.context_min_relevance_threshold = 0.3
        self.mock_settings.context_compression_enabled = True
        
        with patch('server.services.conversation.context_optimizer.get_settings', return_value=self.mock_settings):
            self.optimizer = ContextOptimizer()

    def teardown_method(self):
        """Clean up after tests."""
        reset_context_optimizer()

    def create_test_messages(self, count: int = 20) -> List[ChatMessage]:
        """Create test messages for testing."""
        messages = []
        for i in range(count):
            role = "user" if i % 2 == 0 else "assistant"
            content = f"Message {i}: This is test content about various topics like email, search, and general conversation."
            messages.append(ChatMessage(
                role=role,
                content=content,
                timestamp=f"2024-01-01 {10 + i//10:02d}:{i%60:02d}:00"
            ))
        return messages

    def test_optimizer_initialization(self):
        """Test optimizer initialization with settings."""
        assert self.optimizer.max_context_tokens == 8000
        assert self.optimizer.recent_messages_count == 10
        assert self.optimizer.min_relevance_threshold == 0.3
        assert self.optimizer.optimization_enabled is True

    def test_optimize_context_empty_messages(self):
        """Test optimization with empty message list."""
        result = self.optimizer.optimize_context(
            messages=[],
            current_query="test query",
            agent_type="interaction"
        )
        
        assert result.optimization_strategy == "empty"
        assert result.original_message_count == 0
        assert result.optimized_message_count == 0
        assert len(result.selected_segments) == 0

    def test_optimize_context_disabled(self):
        """Test optimization when disabled."""
        self.mock_settings.context_optimization_enabled = False
        
        with patch('server.services.conversation.context_optimizer.get_settings', return_value=self.mock_settings):
            optimizer = ContextOptimizer()
            messages = self.create_test_messages(5)
            
            result = optimizer.optimize_context(
                messages=messages,
                current_query="test query",
                agent_type="interaction"
            )
            
            assert result.optimization_strategy == "full_context"
            assert result.original_message_count == result.optimized_message_count

    def test_optimize_context_small_conversation(self):
        """Test optimization with small conversation (full context strategy)."""
        messages = self.create_test_messages(5)
        
        result = self.optimizer.optimize_context(
            messages=messages,
            current_query="test query",
            agent_type="interaction"
        )
        
        assert result.optimization_strategy == "full_context"
        assert result.original_message_count == 5
        assert result.optimized_message_count == 5
        assert result.compression_ratio == 1.0

    def test_optimize_context_medium_conversation(self):
        """Test optimization with medium conversation (smart selection strategy)."""
        messages = self.create_test_messages(25)
        
        result = self.optimizer.optimize_context(
            messages=messages,
            current_query="test query about email search",
            agent_type="interaction"
        )
        
        assert result.optimization_strategy == "smart_selection"
        assert result.original_message_count == 25
        assert result.optimized_message_count < 25
        assert result.compression_ratio < 1.0

    def test_optimize_context_large_conversation(self):
        """Test optimization with large conversation (recent only strategy)."""
        # Create messages that exceed token limit
        messages = []
        for i in range(100):
            content = f"Message {i}: " + "This is a very long message with lots of content. " * 20
            messages.append(ChatMessage(
                role="user" if i % 2 == 0 else "assistant",
                content=content,
                timestamp=f"2024-01-01 {10 + i//10:02d}:{i%60:02d}:00"
            ))
        
        result = self.optimizer.optimize_context(
            messages=messages,
            current_query="test query",
            agent_type="interaction"
        )
        
        assert result.optimization_strategy == "recent_only"
        assert result.original_message_count == 100
        assert result.optimized_message_count <= self.optimizer.recent_messages_count

    def test_relevance_scoring(self):
        """Test relevance scoring for different content types."""
        messages = [
            ChatMessage(role="user", content="I need help with email search", timestamp="2024-01-01 10:00:00"),
            ChatMessage(role="assistant", content="I can help you search emails", timestamp="2024-01-01 10:01:00"),
            ChatMessage(role="user", content="What's the weather like?", timestamp="2024-01-01 10:02:00"),
            ChatMessage(role="assistant", content="I don't have weather information", timestamp="2024-01-01 10:03:00"),
        ]
        
        # Test with email-related query
        result = self.optimizer.optimize_context(
            messages=messages,
            current_query="Help me search for emails from John",
            agent_type="interaction"
        )
        
        # Should prioritize email-related messages
        assert result.optimization_strategy in ["smart_selection", "full_context"]
        assert result.original_message_count == 4

    def test_agent_type_scoring(self):
        """Test agent-specific relevance scoring."""
        messages = [
            ChatMessage(role="user", content="Execute email search task", timestamp="2024-01-01 10:00:00"),
            ChatMessage(role="agent", content="Tool/Action: Searching Gmail", timestamp="2024-01-01 10:01:00"),
            ChatMessage(role="user", content="What's your favorite color?", timestamp="2024-01-01 10:02:00"),
        ]
        
        # Test with execution agent
        result = self.optimizer.optimize_context(
            messages=messages,
            current_query="Run email search",
            agent_type="execution"
        )
        
        assert result.optimization_strategy in ["smart_selection", "full_context"]
        assert result.original_message_count == 3

    def test_context_segments(self):
        """Test context segmentation."""
        messages = self.create_test_messages(30)
        
        result = self.optimizer.optimize_context(
            messages=messages,
            current_query="test query",
            agent_type="interaction"
        )
        
        if result.optimization_strategy == "smart_selection":
            assert len(result.selected_segments) > 0
            for segment in result.selected_segments:
                assert isinstance(segment, ContextSegment)
                assert segment.relevance_score >= 0.0
                assert segment.relevance_score <= 1.0
                assert segment.relevance_level in ContextRelevanceLevel

    def test_token_estimation(self):
        """Test token estimation."""
        messages = [
            ChatMessage(role="user", content="Short message", timestamp="2024-01-01 10:00:00"),
            ChatMessage(role="assistant", content="This is a much longer message with more content to test token estimation", timestamp="2024-01-01 10:01:00"),
        ]
        
        tokens = self.optimizer._estimate_tokens(messages)
        assert tokens > 0
        assert isinstance(tokens, int)

    def test_relevance_level_conversion(self):
        """Test score to relevance level conversion."""
        assert self.optimizer._score_to_level(0.9) == ContextRelevanceLevel.CRITICAL
        assert self.optimizer._score_to_level(0.7) == ContextRelevanceLevel.HIGH
        assert self.optimizer._score_to_level(0.5) == ContextRelevanceLevel.MEDIUM
        assert self.optimizer._score_to_level(0.3) == ContextRelevanceLevel.LOW
        assert self.optimizer._score_to_level(0.1) == ContextRelevanceLevel.IRRELEVANT

    def test_content_similarity(self):
        """Test content similarity calculation."""
        messages = [
            ChatMessage(role="user", content="I need help with email search", timestamp="2024-01-01 10:00:00"),
            ChatMessage(role="assistant", content="I can help you search emails", timestamp="2024-01-01 10:01:00"),
        ]
        
        segment = ContextSegment(
            messages=messages,
            relevance_score=0.0,
            relevance_level=ContextRelevanceLevel.MEDIUM,
            segment_type="test",
            start_index=0,
            end_index=1
        )
        
        similarity = self.optimizer._calculate_content_similarity(segment, "email search help")
        assert similarity >= 0.0
        assert similarity <= 1.0

    def test_agent_relevance(self):
        """Test agent-specific relevance calculation."""
        messages = [
            ChatMessage(role="user", content="Execute email search task", timestamp="2024-01-01 10:00:00"),
            ChatMessage(role="agent", content="Tool/Action: Searching Gmail", timestamp="2024-01-01 10:01:00"),
        ]
        
        segment = ContextSegment(
            messages=messages,
            relevance_score=0.0,
            relevance_level=ContextRelevanceLevel.MEDIUM,
            segment_type="test",
            start_index=0,
            end_index=1
        )
        
        relevance = self.optimizer._calculate_agent_relevance(segment, "execution")
        assert relevance >= 0.0
        assert relevance <= 1.0

    def test_max_tokens_override(self):
        """Test max tokens parameter override."""
        messages = self.create_test_messages(50)
        
        result = self.optimizer.optimize_context(
            messages=messages,
            current_query="test query",
            agent_type="interaction",
            max_tokens=1000  # Override default
        )
        
        assert result.total_tokens_estimate <= 1000

    def test_get_optimization_stats(self):
        """Test getting optimization statistics."""
        stats = self.optimizer.get_optimization_stats()
        
        assert "max_context_tokens" in stats
        assert "recent_messages_count" in stats
        assert "min_relevance_threshold" in stats
        assert "optimization_strategies" in stats
        assert stats["max_context_tokens"] == 8000
        assert stats["recent_messages_count"] == 10


class TestContextOptimizationResult:
    """Test cases for ContextOptimizationResult class."""

    def test_result_initialization(self):
        """Test result initialization and compression ratio calculation."""
        result = ContextOptimizationResult(
            selected_segments=[],
            total_tokens_estimate=1000,
            optimization_strategy="test",
            original_message_count=10,
            optimized_message_count=5
        )
        
        assert result.compression_ratio == 0.5
        assert result.optimization_strategy == "test"
        assert result.original_message_count == 10
        assert result.optimized_message_count == 5

    def test_result_empty_original(self):
        """Test result with empty original message count."""
        result = ContextOptimizationResult(
            selected_segments=[],
            total_tokens_estimate=0,
            optimization_strategy="empty",
            original_message_count=0,
            optimized_message_count=0
        )
        
        assert result.compression_ratio == 1.0


class TestContextSegment:
    """Test cases for ContextSegment class."""

    def test_segment_initialization(self):
        """Test segment initialization and content length calculation."""
        messages = [
            ChatMessage(role="user", content="Hello", timestamp="2024-01-01 10:00:00"),
            ChatMessage(role="assistant", content="Hi there", timestamp="2024-01-01 10:01:00"),
        ]
        
        segment = ContextSegment(
            messages=messages,
            relevance_score=0.8,
            relevance_level=ContextRelevanceLevel.HIGH,
            segment_type="recent",
            start_index=0,
            end_index=1
        )
        
        assert segment.content_length == 13  # "Hello" + "Hi there"
        assert segment.relevance_score == 0.8
        assert segment.relevance_level == ContextRelevanceLevel.HIGH
        assert segment.segment_type == "recent"


class TestGlobalOptimizer:
    """Test cases for global optimizer functions."""

    def test_get_context_optimizer(self):
        """Test getting global optimizer instance."""
        optimizer1 = get_context_optimizer()
        optimizer2 = get_context_optimizer()
        
        # Should return the same instance
        assert optimizer1 is optimizer2
        assert isinstance(optimizer1, ContextOptimizer)

    def test_reset_context_optimizer(self):
        """Test resetting global optimizer."""
        optimizer1 = get_context_optimizer()
        reset_context_optimizer()
        optimizer2 = get_context_optimizer()
        
        # Should return different instances after reset
        assert optimizer1 is not optimizer2


if __name__ == "__main__":
    pytest.main([__file__])
