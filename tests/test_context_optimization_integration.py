"""Integration tests for context optimization system."""

import pytest
import asyncio
from unittest.mock import Mock, patch, MagicMock
from typing import List, Dict, Any

from server.services.conversation.context_optimizer import get_context_optimizer, reset_context_optimizer
from server.services.conversation.context_metrics import get_context_optimization_monitor, reset_context_optimization_monitor
from server.agents.interaction_agent.agent import prepare_message_with_smart_context
from server.agents.execution_agent.agent import ExecutionAgent
from server.models import ChatMessage
from server.routes.context_optimization import preview_context_optimization, ContextPreviewRequest


class TestContextOptimizationIntegration:
    """Integration tests for the complete context optimization system."""

    def setup_method(self):
        """Set up test fixtures."""
        # Reset global instances for clean tests
        reset_context_optimizer()
        reset_context_optimization_monitor()

    def teardown_method(self):
        """Clean up after tests."""
        reset_context_optimizer()
        reset_context_optimization_monitor()

    def create_large_conversation(self, count: int = 50) -> List[ChatMessage]:
        """Create a large conversation for testing."""
        messages = []
        topics = ["email", "search", "weather", "calendar", "meeting", "project", "task", "reminder"]
        
        for i in range(count):
            role = "user" if i % 2 == 0 else "assistant"
            topic = topics[i % len(topics)]
            content = f"Message {i}: This is about {topic}. " + f"Some additional content about {topic} and related topics. " * 5
            messages.append(ChatMessage(
                role=role,
                content=content,
                timestamp=f"2024-01-01 {10 + i//10:02d}:{i%60:02d}:00"
            ))
        
        return messages

    @patch('server.services.conversation.context_optimizer.get_settings')
    def test_end_to_end_optimization_flow(self, mock_get_settings):
        """Test complete optimization flow from messages to final result."""
        # Mock settings
        mock_settings = Mock()
        mock_settings.context_optimization_enabled = True
        mock_settings.context_max_tokens = 8000
        mock_settings.context_recent_messages_count = 10
        mock_settings.context_min_relevance_threshold = 0.3
        mock_settings.context_compression_enabled = True
        mock_get_settings.return_value = mock_settings

        # Create test conversation
        messages = self.create_large_conversation(30)
        current_query = "Help me find emails about project management"

        # Get optimizer
        optimizer = get_context_optimizer()

        # Test optimization
        result = optimizer.optimize_context(
            messages=messages,
            current_query=current_query,
            agent_type="interaction"
        )

        # Verify result
        assert result.original_message_count == 30
        assert result.optimized_message_count < 30
        assert result.compression_ratio < 1.0
        assert result.total_tokens_estimate > 0
        assert len(result.selected_segments) > 0

        # Verify metrics were recorded
        monitor = get_context_optimization_monitor()
        metrics = monitor.get_metrics_summary()
        assert metrics["total_optimizations"] == 1
        assert metrics["avg_compression_ratio"] < 1.0

    @patch('server.services.conversation.context_optimizer.get_settings')
    def test_interaction_agent_integration(self, mock_get_settings):
        """Test interaction agent integration with context optimization."""
        # Mock settings
        mock_settings = Mock()
        mock_settings.context_optimization_enabled = True
        mock_settings.context_max_tokens = 8000
        mock_settings.context_recent_messages_count = 10
        mock_settings.context_min_relevance_threshold = 0.3
        mock_settings.context_compression_enabled = True
        mock_get_settings.return_value = mock_settings

        # Create test conversation
        messages = self.create_large_conversation(25)
        current_query = "Search for emails from John about the project"

        # Test interaction agent context preparation
        result = prepare_message_with_smart_context(
            latest_text=current_query,
            messages=messages,
            message_type="user"
        )

        # Verify result structure
        assert len(result) == 1
        assert result[0]["role"] == "user"
        content = result[0]["content"]
        
        # Should contain conversation history, active agents, and current turn
        assert "<conversation_history>" in content
        assert "<active_agents>" in content
        assert "<new_user_message>" in content
        assert current_query in content

    @patch('server.services.conversation.context_optimizer.get_settings')
    def test_execution_agent_integration(self, mock_get_settings):
        """Test execution agent integration with context optimization."""
        # Mock settings
        mock_settings = Mock()
        mock_settings.context_optimization_enabled = True
        mock_settings.context_max_tokens = 8000
        mock_settings.context_recent_messages_count = 10
        mock_settings.context_min_relevance_threshold = 0.3
        mock_settings.context_compression_enabled = True
        mock_get_settings.return_value = mock_settings

        # Create execution agent
        agent = ExecutionAgent("test-execution-agent")
        agent._log_store = Mock()

        # Create test transcript
        transcript = """
<agent_request timestamp="2024-01-01 10:00:00">Search for emails from John about project management</agent_request>
<agent_response timestamp="2024-01-01 10:01:00">I'll search for emails from John about project management</agent_response>
<action timestamp="2024-01-01 10:02:00">Calling gmail_search with: query=from:john project management</action>
<tool_response timestamp="2024-01-01 10:03:00">Found 3 emails from John about project management</tool_response>
<agent_response timestamp="2024-01-01 10:04:00">I found 3 emails from John about project management</agent_response>
<agent_request timestamp="2024-01-01 10:05:00">Show me the most recent one</agent_request>
<agent_response timestamp="2024-01-01 10:06:00">Here's the most recent email from John about project management</agent_response>
"""
        agent._log_store.load_transcript.return_value = transcript

        # Test smart context system prompt
        result = agent.build_system_prompt_with_smart_context("Show me the email content")

        # Verify result
        assert "# Execution History" in result
        assert "test-execution-agent" in result  # Agent name in base prompt
        assert "Search for emails from John" in result

    @patch('server.services.conversation.context_optimizer.get_settings')
    def test_context_preview_api_integration(self, mock_get_settings):
        """Test context preview API integration."""
        # Mock settings
        mock_settings = Mock()
        mock_settings.context_optimization_enabled = True
        mock_settings.context_max_tokens = 8000
        mock_settings.context_recent_messages_count = 10
        mock_settings.context_min_relevance_threshold = 0.3
        mock_settings.context_compression_enabled = True
        mock_get_settings.return_value = mock_settings

        # Create test request
        messages_data = [
            {"role": "user", "content": "Hello, how are you?", "timestamp": "2024-01-01 10:00:00"},
            {"role": "assistant", "content": "I'm doing well, thank you!", "timestamp": "2024-01-01 10:01:00"},
            {"role": "user", "content": "Can you help me with email search?", "timestamp": "2024-01-01 10:02:00"},
            {"role": "assistant", "content": "Of course! What do you need to search for?", "timestamp": "2024-01-01 10:03:00"},
            {"role": "user", "content": "I need to find emails from John about the project", "timestamp": "2024-01-01 10:04:00"},
            {"role": "assistant", "content": "I'll help you search for emails from John about the project", "timestamp": "2024-01-01 10:05:00"},
            {"role": "agent", "content": "Tool/Action: Searching Gmail for emails from John about project", "timestamp": "2024-01-01 10:06:00"},
            {"role": "agent", "content": "Found 5 emails from John about the project", "timestamp": "2024-01-01 10:07:00"},
            {"role": "assistant", "content": "I found 5 emails from John about the project. Would you like me to show them?", "timestamp": "2024-01-01 10:08:00"},
            {"role": "user", "content": "Yes, please show me the most recent one", "timestamp": "2024-01-01 10:09:00"},
        ]

        request = ContextPreviewRequest(
            messages=messages_data,
            current_query="Show me the most recent email from John about the project",
            agent_type="interaction"
        )

        # Test preview generation
        async def run_preview():
            return await preview_context_optimization(request)

        preview_result = asyncio.run(run_preview())

        # Verify result structure
        assert preview_result.success is True
        assert "original_context" in preview_result.dict()
        assert "optimized_context" in preview_result.dict()
        assert "comparison" in preview_result.dict()

        # Verify original context
        original = preview_result.original_context
        assert original["message_count"] == 10
        assert original["strategy"] == "full_context"

        # Verify optimized context
        optimized = preview_result.optimized_context
        assert optimized["message_count"] <= 10
        assert optimized["compression_ratio"] <= 1.0
        assert "segments" in optimized

        # Verify comparison
        comparison = preview_result.comparison
        assert comparison["message_reduction"] >= 0
        assert comparison["token_reduction"] >= 0
        assert comparison["compression_ratio"] <= 1.0

    @patch('server.services.conversation.context_optimizer.get_settings')
    def test_metrics_integration(self, mock_get_settings):
        """Test metrics collection integration."""
        # Mock settings
        mock_settings = Mock()
        mock_settings.context_optimization_enabled = True
        mock_settings.context_max_tokens = 8000
        mock_settings.context_recent_messages_count = 10
        mock_settings.context_min_relevance_threshold = 0.3
        mock_settings.context_compression_enabled = True
        mock_get_settings.return_value = mock_settings

        # Get monitor
        monitor = get_context_optimization_monitor()

        # Perform multiple optimizations
        optimizer = get_context_optimizer()
        messages = self.create_large_conversation(20)

        for i in range(5):
            result = optimizer.optimize_context(
                messages=messages,
                current_query=f"Test query {i}",
                agent_type="interaction" if i % 2 == 0 else "execution"
            )

        # Verify metrics
        metrics = monitor.get_metrics_summary()
        assert metrics["total_optimizations"] == 5
        assert metrics["total_original_messages"] == 100  # 5 * 20
        assert metrics["total_optimized_messages"] < 100
        assert metrics["agent_type_distribution"]["interaction"] == 3
        assert metrics["agent_type_distribution"]["execution"] == 2

        # Test performance stats
        performance = monitor.get_performance_stats()
        assert "compression_stats" in performance
        assert "processing_stats" in performance

        # Test recent optimizations
        recent = monitor.get_recent_optimizations(3)
        assert len(recent) == 3
        assert recent[0]["strategy"] in ["smart_selection", "recent_only", "full_context"]

    @patch('server.services.conversation.context_optimizer.get_settings')
    def test_different_optimization_strategies(self, mock_get_settings):
        """Test different optimization strategies based on conversation size."""
        # Mock settings
        mock_settings = Mock()
        mock_settings.context_optimization_enabled = True
        mock_settings.context_max_tokens = 8000
        mock_settings.context_recent_messages_count = 10
        mock_settings.context_min_relevance_threshold = 0.3
        mock_settings.context_compression_enabled = True
        mock_get_settings.return_value = mock_settings

        optimizer = get_context_optimizer()

        # Test small conversation (full context)
        small_messages = self.create_large_conversation(5)
        result = optimizer.optimize_context(
            messages=small_messages,
            current_query="test query",
            agent_type="interaction"
        )
        assert result.optimization_strategy == "full_context"

        # Test medium conversation (smart selection)
        medium_messages = self.create_large_conversation(25)
        result = optimizer.optimize_context(
            messages=medium_messages,
            current_query="test query",
            agent_type="interaction"
        )
        assert result.optimization_strategy == "smart_selection"

        # Test large conversation (recent only)
        large_messages = []
        for i in range(100):
            content = f"Message {i}: " + "This is a very long message with lots of content. " * 50
            large_messages.append(ChatMessage(
                role="user" if i % 2 == 0 else "assistant",
                content=content,
                timestamp=f"2024-01-01 {10 + i//10:02d}:{i%60:02d}:00"
            ))

        result = optimizer.optimize_context(
            messages=large_messages,
            current_query="test query",
            agent_type="interaction"
        )
        assert result.optimization_strategy == "recent_only"

    @patch('server.services.conversation.context_optimizer.get_settings')
    def test_error_handling_integration(self, mock_get_settings):
        """Test error handling in integration scenarios."""
        # Mock settings
        mock_settings = Mock()
        mock_settings.context_optimization_enabled = True
        mock_settings.context_max_tokens = 8000
        mock_settings.context_recent_messages_count = 10
        mock_settings.context_min_relevance_threshold = 0.3
        mock_settings.context_compression_enabled = True
        mock_get_settings.return_value = mock_settings

        optimizer = get_context_optimizer()

        # Test with None messages
        result = optimizer.optimize_context(
            messages=None,
            current_query="test query",
            agent_type="interaction"
        )
        assert result.optimization_strategy == "empty"

        # Test with malformed messages
        malformed_messages = [
            ChatMessage(role="user", content="", timestamp=""),  # Empty content
            ChatMessage(role="", content="test", timestamp=""),  # Empty role
        ]
        
        result = optimizer.optimize_context(
            messages=malformed_messages,
            current_query="test query",
            agent_type="interaction"
        )
        # Should handle gracefully
        assert result.original_message_count == 2

    @patch('server.services.conversation.context_optimizer.get_settings')
    def test_concurrent_optimization(self, mock_get_settings):
        """Test concurrent optimization requests."""
        # Mock settings
        mock_settings = Mock()
        mock_settings.context_optimization_enabled = True
        mock_settings.context_max_tokens = 8000
        mock_settings.context_recent_messages_count = 10
        mock_settings.context_min_relevance_threshold = 0.3
        mock_settings.context_compression_enabled = True
        mock_get_settings.return_value = mock_settings

        optimizer = get_context_optimizer()
        messages = self.create_large_conversation(20)

        async def optimize_concurrent(query_id: int):
            return optimizer.optimize_context(
                messages=messages,
                current_query=f"Concurrent query {query_id}",
                agent_type="interaction"
            )

        # Run concurrent optimizations
        async def run_concurrent():
            tasks = [optimize_concurrent(i) for i in range(5)]
            return await asyncio.gather(*tasks)

        results = asyncio.run(run_concurrent())

        # Verify all optimizations completed
        assert len(results) == 5
        for result in results:
            assert result.original_message_count == 20
            assert result.optimized_message_count <= 20

        # Verify metrics were recorded for all
        monitor = get_context_optimization_monitor()
        metrics = monitor.get_metrics_summary()
        assert metrics["total_optimizations"] == 5


class TestContextOptimizationPerformance:
    """Performance tests for context optimization."""

    def setup_method(self):
        """Set up test fixtures."""
        reset_context_optimizer()
        reset_context_optimization_monitor()

    def teardown_method(self):
        """Clean up after tests."""
        reset_context_optimizer()
        reset_context_optimization_monitor()

    @patch('server.services.conversation.context_optimizer.get_settings')
    def test_optimization_performance(self, mock_get_settings):
        """Test optimization performance with large conversations."""
        import time

        # Mock settings
        mock_settings = Mock()
        mock_settings.context_optimization_enabled = True
        mock_settings.context_max_tokens = 8000
        mock_settings.context_recent_messages_count = 10
        mock_settings.context_min_relevance_threshold = 0.3
        mock_settings.context_compression_enabled = True
        mock_get_settings.return_value = mock_settings

        optimizer = get_context_optimizer()

        # Test with different conversation sizes
        sizes = [10, 50, 100, 200]
        
        for size in sizes:
            messages = []
            for i in range(size):
                content = f"Message {i}: " + "This is test content. " * 10
                messages.append(ChatMessage(
                    role="user" if i % 2 == 0 else "assistant",
                    content=content,
                    timestamp=f"2024-01-01 {10 + i//10:02d}:{i%60:02d}:00"
                ))

            start_time = time.time()
            result = optimizer.optimize_context(
                messages=messages,
                current_query="test query",
                agent_type="interaction"
            )
            end_time = time.time()

            processing_time = end_time - start_time
            
            # Verify reasonable performance (should be under 1 second for most cases)
            assert processing_time < 1.0, f"Optimization took too long for size {size}: {processing_time:.3f}s"
            
            # Verify compression
            assert result.compression_ratio <= 1.0
            assert result.optimized_message_count <= result.original_message_count


if __name__ == "__main__":
    pytest.main([__file__])
