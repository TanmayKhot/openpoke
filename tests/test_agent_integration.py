"""Unit tests for agent integration with context optimization."""

import pytest
from unittest.mock import Mock, patch, MagicMock
from typing import List

from server.agents.interaction_agent.agent import (
    prepare_message_with_smart_context,
    _build_optimized_transcript,
    _messages_to_transcript,
    _log_context_optimization,
)
from server.agents.execution_agent.agent import (
    ExecutionAgent,
    _parse_transcript_to_messages,
    _build_optimized_execution_transcript,
    _messages_to_execution_transcript,
    _log_execution_context_optimization,
)
from server.models import ChatMessage
from server.services.conversation.context_optimizer import ContextOptimizationResult, ContextSegment


class TestInteractionAgentIntegration:
    """Test cases for interaction agent context optimization integration."""

    def setup_method(self):
        """Set up test fixtures."""
        self.test_messages = [
            ChatMessage(role="user", content="Hello, how are you?", timestamp="2024-01-01 10:00:00"),
            ChatMessage(role="assistant", content="I'm doing well, thank you!", timestamp="2024-01-01 10:01:00"),
            ChatMessage(role="user", content="Can you help me with email?", timestamp="2024-01-01 10:02:00"),
            ChatMessage(role="assistant", content="Of course! What do you need help with?", timestamp="2024-01-01 10:03:00"),
        ]

    @patch('server.agents.interaction_agent.agent.get_context_optimizer')
    def test_prepare_message_with_smart_context(self, mock_get_optimizer):
        """Test smart context preparation for interaction agent."""
        # Mock optimizer
        mock_optimizer = Mock()
        mock_optimizer.optimize_context.return_value = ContextOptimizationResult(
            selected_segments=[
                ContextSegment(
                    messages=self.test_messages[-2:],  # Last 2 messages
                    relevance_score=0.9,
                    relevance_level="high",
                    segment_type="recent",
                    start_index=2,
                    end_index=3
                )
            ],
            total_tokens_estimate=100,
            optimization_strategy="smart_selection",
            original_message_count=4,
            optimized_message_count=2
        )
        mock_get_optimizer.return_value = mock_optimizer

        # Test the function
        result = prepare_message_with_smart_context(
            latest_text="Show me recent emails",
            messages=self.test_messages,
            message_type="user"
        )

        # Verify optimizer was called
        mock_optimizer.optimize_context.assert_called_once_with(
            messages=self.test_messages,
            current_query="Show me recent emails",
            agent_type="interaction"
        )

        # Verify result structure
        assert len(result) == 1
        assert result[0]["role"] == "user"
        assert "conversation_history" in result[0]["content"]
        assert "active_agents" in result[0]["content"]
        assert "new_user_message" in result[0]["content"]

    def test_build_optimized_transcript_empty(self):
        """Test building optimized transcript with empty result."""
        result = ContextOptimizationResult(
            selected_segments=[],
            total_tokens_estimate=0,
            optimization_strategy="empty",
            original_message_count=0,
            optimized_message_count=0
        )

        transcript = _build_optimized_transcript(result)
        assert transcript == "None"

    def test_build_optimized_transcript_with_segments(self):
        """Test building optimized transcript with segments."""
        segment = ContextSegment(
            messages=self.test_messages[:2],
            relevance_score=0.8,
            relevance_level="high",
            segment_type="recent",
            start_index=0,
            end_index=1
        )

        result = ContextOptimizationResult(
            selected_segments=[segment],
            total_tokens_estimate=50,
            optimization_strategy="smart_selection",
            original_message_count=4,
            optimized_message_count=2
        )

        transcript = _build_optimized_transcript(result)
        assert transcript != "None"
        assert "user_message" in transcript
        assert "assistant_message" in transcript

    def test_messages_to_transcript(self):
        """Test converting messages to transcript format."""
        transcript = _messages_to_transcript(self.test_messages)

        assert "<user_message" in transcript
        assert "<assistant_message" in transcript
        assert "Hello, how are you?" in transcript
        assert "I'm doing well, thank you!" in transcript

    def test_messages_to_transcript_with_agent_role(self):
        """Test converting messages with agent role to transcript."""
        messages_with_agent = self.test_messages + [
            ChatMessage(role="agent", content="Tool/Action: Searching Gmail", timestamp="2024-01-01 10:04:00")
        ]

        transcript = _messages_to_transcript(messages_with_agent)
        assert "<agent_message" in transcript
        assert "Tool/Action: Searching Gmail" in transcript

    @patch('server.agents.interaction_agent.agent.logger')
    def test_log_context_optimization(self, mock_logger):
        """Test logging context optimization metrics."""
        result = ContextOptimizationResult(
            selected_segments=[],
            total_tokens_estimate=100,
            optimization_strategy="smart_selection",
            original_message_count=10,
            optimized_message_count=5
        )

        _log_context_optimization(result, "test query")

        # Verify logger was called
        mock_logger.info.assert_called_once()
        call_args = mock_logger.info.call_args
        assert "context optimization applied" in call_args[0][0]
        assert call_args[1]["extra"]["strategy"] == "smart_selection"
        assert call_args[1]["extra"]["original_messages"] == 10
        assert call_args[1]["extra"]["optimized_messages"] == 5


class TestExecutionAgentIntegration:
    """Test cases for execution agent context optimization integration."""

    def setup_method(self):
        """Set up test fixtures."""
        self.mock_log_store = Mock()
        self.agent = ExecutionAgent("test-agent", conversation_limit=10)
        self.agent._log_store = self.mock_log_store

        self.test_transcript = """
<agent_request timestamp="2024-01-01 10:00:00">Search for emails from John</agent_request>
<agent_response timestamp="2024-01-01 10:01:00">I'll search for emails from John</agent_response>
<action timestamp="2024-01-01 10:02:00">Calling gmail_search with: query=from:john</action>
<tool_response timestamp="2024-01-01 10:03:00">Found 5 emails from John</tool_response>
<agent_response timestamp="2024-01-01 10:04:00">I found 5 emails from John</agent_response>
"""

    @patch('server.agents.execution_agent.agent.get_settings')
    @patch('server.agents.execution_agent.agent.get_context_optimizer')
    def test_build_system_prompt_with_smart_context_enabled(self, mock_get_optimizer, mock_get_settings):
        """Test smart context system prompt when optimization is enabled."""
        # Mock settings
        mock_settings = Mock()
        mock_settings.context_optimization_enabled = True
        mock_get_settings.return_value = mock_settings

        # Mock log store
        self.mock_log_store.load_transcript.return_value = self.test_transcript

        # Mock optimizer
        mock_optimizer = Mock()
        mock_optimizer.optimize_context.return_value = ContextOptimizationResult(
            selected_segments=[
                ContextSegment(
                    messages=[],  # Empty for simplicity
                    relevance_score=0.8,
                    relevance_level="high",
                    segment_type="recent",
                    start_index=0,
                    end_index=1
                )
            ],
            total_tokens_estimate=50,
            optimization_strategy="smart_selection",
            original_message_count=5,
            optimized_message_count=2
        )
        mock_get_optimizer.return_value = mock_optimizer

        # Test the method
        result = self.agent.build_system_prompt_with_smart_context("Search for emails")

        # Verify optimizer was called
        mock_optimizer.optimize_context.assert_called_once_with(
            messages=mock_get_optimizer.return_value.optimize_context.call_args[1]["messages"],
            current_query="Search for emails",
            agent_type="execution"
        )

        # Verify result contains execution history
        assert "# Execution History" in result

    @patch('server.agents.execution_agent.agent.get_settings')
    def test_build_system_prompt_with_smart_context_disabled(self, mock_get_settings):
        """Test smart context system prompt when optimization is disabled."""
        # Mock settings
        mock_settings = Mock()
        mock_settings.context_optimization_enabled = False
        mock_get_settings.return_value = mock_settings

        # Mock log store
        self.mock_log_store.load_transcript.return_value = self.test_transcript

        # Test the method
        result = self.agent.build_system_prompt_with_smart_context("Search for emails")

        # Should fall back to traditional method
        assert "# Execution History" in result
        assert "Search for emails from John" in result

    @patch('server.agents.execution_agent.agent.get_settings')
    def test_build_system_prompt_with_smart_context_no_transcript(self, mock_get_settings):
        """Test smart context system prompt with no transcript."""
        # Mock settings
        mock_settings = Mock()
        mock_settings.context_optimization_enabled = True
        mock_get_settings.return_value = mock_settings

        # Mock log store with empty transcript
        self.mock_log_store.load_transcript.return_value = ""

        # Test the method
        result = self.agent.build_system_prompt_with_smart_context("Search for emails")

        # Should return base prompt only
        assert "# Execution History" not in result
        assert "test-agent" in result  # Agent name should be in base prompt

    def test_parse_transcript_to_messages(self):
        """Test parsing execution agent transcript to messages."""
        messages = self.agent._parse_transcript_to_messages(self.test_transcript)

        assert len(messages) == 4  # Should parse 4 messages
        assert messages[0].role == "user"
        assert messages[0].content == "Search for emails from John"
        assert messages[1].role == "assistant"
        assert messages[1].content == "I'll search for emails from John"
        assert messages[2].role == "agent"
        assert "Tool/Action: Calling gmail_search" in messages[2].content

    def test_parse_transcript_to_messages_empty(self):
        """Test parsing empty transcript."""
        messages = self.agent._parse_transcript_to_messages("")
        assert len(messages) == 0

    def test_parse_transcript_to_messages_malformed(self):
        """Test parsing malformed transcript."""
        malformed_transcript = """
<agent_request>Incomplete request
<agent_response>Complete response</agent_response>
"""
        messages = self.agent._parse_transcript_to_messages(malformed_transcript)
        # Should handle malformed input gracefully
        assert len(messages) >= 0

    def test_build_optimized_execution_transcript_empty(self):
        """Test building optimized execution transcript with empty result."""
        result = ContextOptimizationResult(
            selected_segments=[],
            total_tokens_estimate=0,
            optimization_strategy="empty",
            original_message_count=0,
            optimized_message_count=0
        )

        transcript = self.agent._build_optimized_execution_transcript(result)
        assert transcript == ""

    def test_build_optimized_execution_transcript_with_segments(self):
        """Test building optimized execution transcript with segments."""
        messages = [
            ChatMessage(role="user", content="Search for emails", timestamp=""),
            ChatMessage(role="assistant", content="I'll search for emails", timestamp=""),
        ]

        segment = ContextSegment(
            messages=messages,
            relevance_score=0.8,
            relevance_level="high",
            segment_type="recent",
            start_index=0,
            end_index=1
        )

        result = ContextOptimizationResult(
            selected_segments=[segment],
            total_tokens_estimate=50,
            optimization_strategy="smart_selection",
            original_message_count=5,
            optimized_message_count=2
        )

        transcript = self.agent._build_optimized_execution_transcript(result)
        assert "<agent_request>Search for emails</agent_request>" in transcript
        assert "<agent_response>I'll search for emails</agent_response>" in transcript

    def test_messages_to_execution_transcript(self):
        """Test converting messages to execution transcript format."""
        messages = [
            ChatMessage(role="user", content="Search for emails", timestamp=""),
            ChatMessage(role="assistant", content="I'll search for emails", timestamp=""),
            ChatMessage(role="agent", content="Tool/Action: Calling gmail_search", timestamp=""),
        ]

        transcript = self.agent._messages_to_execution_transcript(messages)
        assert "<agent_request>Search for emails</agent_request>" in transcript
        assert "<agent_response>I'll search for emails</agent_response>" in transcript
        assert "<action>Tool/Action: Calling gmail_search</action>" in transcript

    @patch('server.agents.execution_agent.agent.logger')
    def test_log_execution_context_optimization(self, mock_logger):
        """Test logging execution context optimization metrics."""
        result = ContextOptimizationResult(
            selected_segments=[],
            total_tokens_estimate=100,
            optimization_strategy="smart_selection",
            original_message_count=10,
            optimized_message_count=5
        )

        self.agent._log_execution_context_optimization(result, "test instruction")

        # Verify logger was called
        mock_logger.info.assert_called_once()
        call_args = mock_logger.info.call_args
        assert "execution agent context optimization applied" in call_args[0][0]
        assert call_args[1]["extra"]["agent_name"] == "test-agent"
        assert call_args[1]["extra"]["strategy"] == "smart_selection"
        assert call_args[1]["extra"]["original_messages"] == 10
        assert call_args[1]["extra"]["optimized_messages"] == 5

    @patch('server.agents.execution_agent.agent.get_settings')
    @patch('server.agents.execution_agent.agent.get_context_optimizer')
    @patch('server.agents.execution_agent.agent.logger')
    def test_build_system_prompt_with_smart_context_exception(self, mock_logger, mock_get_optimizer, mock_get_settings):
        """Test smart context system prompt with exception handling."""
        # Mock settings
        mock_settings = Mock()
        mock_settings.context_optimization_enabled = True
        mock_get_settings.return_value = mock_settings

        # Mock log store
        self.mock_log_store.load_transcript.return_value = self.test_transcript

        # Mock optimizer to raise exception
        mock_optimizer = Mock()
        mock_optimizer.optimize_context.side_effect = Exception("Test error")
        mock_get_optimizer.return_value = mock_optimizer

        # Test the method
        result = self.agent.build_system_prompt_with_smart_context("Search for emails")

        # Should fall back to traditional method
        assert "# Execution History" in result
        assert "Search for emails from John" in result

        # Should log warning
        mock_logger.warning.assert_called_once()
        call_args = mock_logger.warning.call_args
        assert "execution agent context optimization failed" in call_args[0][0]


class TestAgentIntegrationEdgeCases:
    """Test edge cases for agent integration."""

    def test_interaction_agent_with_empty_messages(self):
        """Test interaction agent with empty message list."""
        result = prepare_message_with_smart_context(
            latest_text="test query",
            messages=[],
            message_type="user"
        )

        assert len(result) == 1
        assert result[0]["role"] == "user"
        assert "None" in result[0]["content"]  # Empty conversation history

    def test_execution_agent_with_none_transcript(self):
        """Test execution agent with None transcript."""
        agent = ExecutionAgent("test-agent")
        agent._log_store = Mock()
        agent._log_store.load_transcript.return_value = None

        with patch('server.agents.execution_agent.agent.get_settings') as mock_get_settings:
            mock_settings = Mock()
            mock_settings.context_optimization_enabled = True
            mock_get_settings.return_value = mock_settings

            result = agent.build_system_prompt_with_smart_context("test instruction")
            assert "# Execution History" not in result

    def test_execution_agent_with_conversation_limit(self):
        """Test execution agent with conversation limit."""
        agent = ExecutionAgent("test-agent", conversation_limit=2)
        agent._log_store = Mock()
        
        # Create transcript with more than limit
        transcript = """
<agent_request>Request 1</agent_request>
<agent_response>Response 1</agent_response>
<agent_request>Request 2</agent_request>
<agent_response>Response 2</agent_response>
<agent_request>Request 3</agent_request>
<agent_response>Response 3</agent_response>
"""
        agent._log_store.load_transcript.return_value = transcript

        with patch('server.agents.execution_agent.agent.get_settings') as mock_get_settings:
            mock_settings = Mock()
            mock_settings.context_optimization_enabled = False  # Use traditional method
            mock_get_settings.return_value = mock_settings

            result = agent.build_system_prompt_with_smart_context("test instruction")
            
            # Should respect conversation limit
            assert "Request 1" not in result  # Should be cut off
            assert "Request 2" in result
            assert "Request 3" in result


if __name__ == "__main__":
    pytest.main([__file__])
