"""Unit tests for context optimization API endpoints."""

import pytest
import asyncio
from unittest.mock import Mock, patch, MagicMock
from typing import Dict, Any, List

from server.routes.context_optimization import (
    preview_context_optimization,
    get_sample_context_preview,
    get_context_optimization_metrics,
    get_context_optimization_summary,
    get_recent_optimizations,
    reset_context_optimization_metrics,
    ContextPreviewRequest,
    ContextPreviewResponse,
)
from server.services.conversation.context_optimizer import ContextOptimizationResult, ContextSegment, ContextRelevanceLevel
from server.services.conversation.context_metrics import get_context_optimization_monitor, reset_context_optimization_monitor
from server.models import ChatMessage


class TestContextPreviewAPI:
    """Test cases for context preview API endpoints."""

    def setup_method(self):
        """Set up test fixtures."""
        reset_context_optimization_monitor()

    def teardown_method(self):
        """Clean up after tests."""
        reset_context_optimization_monitor()

    @patch('server.routes.context_optimization.get_context_optimizer')
    async def test_preview_context_optimization_success(self, mock_get_optimizer):
        """Test successful context optimization preview."""
        # Mock optimizer
        mock_optimizer = Mock()
        
        # Mock original result (full context)
        original_segment = ContextSegment(
            messages=[
                ChatMessage(role="user", content="Hello", timestamp="2024-01-01 10:00:00"),
                ChatMessage(role="assistant", content="Hi there", timestamp="2024-01-01 10:01:00"),
            ],
            relevance_score=1.0,
            relevance_level=ContextRelevanceLevel.CRITICAL,
            segment_type="full",
            start_index=0,
            end_index=1
        )
        
        original_result = ContextOptimizationResult(
            selected_segments=[original_segment],
            total_tokens_estimate=100,
            optimization_strategy="full_context",
            original_message_count=2,
            optimized_message_count=2
        )
        
        # Mock optimized result
        optimized_segment = ContextSegment(
            messages=[
                ChatMessage(role="user", content="Hello", timestamp="2024-01-01 10:00:00"),
            ],
            relevance_score=0.9,
            relevance_level=ContextRelevanceLevel.HIGH,
            segment_type="recent",
            start_index=0,
            end_index=0
        )
        
        optimized_result = ContextOptimizationResult(
            selected_segments=[optimized_segment],
            total_tokens_estimate=50,
            optimization_strategy="smart_selection",
            original_message_count=2,
            optimized_message_count=1
        )
        
        mock_optimizer._optimize_full_context.return_value = original_result
        mock_optimizer.optimize_context.return_value = optimized_result
        mock_get_optimizer.return_value = mock_optimizer

        # Create request
        request = ContextPreviewRequest(
            messages=[
                {"role": "user", "content": "Hello", "timestamp": "2024-01-01 10:00:00"},
                {"role": "assistant", "content": "Hi there", "timestamp": "2024-01-01 10:01:00"},
            ],
            current_query="test query",
            agent_type="interaction"
        )

        # Test preview
        result = await preview_context_optimization(request)

        # Verify result
        assert isinstance(result, ContextPreviewResponse)
        assert result.success is True
        assert result.original_context["strategy"] == "full_context"
        assert result.optimized_context["strategy"] == "smart_selection"
        assert result.comparison["message_reduction"] == 1
        assert result.comparison["token_reduction"] == 50
        assert result.comparison["compression_ratio"] == 0.5

    @patch('server.routes.context_optimization.get_context_optimizer')
    async def test_preview_context_optimization_empty_messages(self, mock_get_optimizer):
        """Test context optimization preview with empty messages."""
        # Mock optimizer
        mock_optimizer = Mock()
        
        empty_result = ContextOptimizationResult(
            selected_segments=[],
            total_tokens_estimate=0,
            optimization_strategy="empty",
            original_message_count=0,
            optimized_message_count=0
        )
        
        mock_optimizer._optimize_full_context.return_value = empty_result
        mock_optimizer.optimize_context.return_value = empty_result
        mock_get_optimizer.return_value = mock_optimizer

        # Create request with empty messages
        request = ContextPreviewRequest(
            messages=[],
            current_query="test query",
            agent_type="interaction"
        )

        # Test preview
        result = await preview_context_optimization(request)

        # Verify result
        assert result.success is True
        assert result.original_context["message_count"] == 0
        assert result.optimized_context["message_count"] == 0
        assert result.comparison["message_reduction"] == 0

    @patch('server.routes.context_optimization.get_context_optimizer')
    async def test_preview_context_optimization_exception(self, mock_get_optimizer):
        """Test context optimization preview with exception."""
        # Mock optimizer to raise exception
        mock_optimizer = Mock()
        mock_optimizer._optimize_full_context.side_effect = Exception("Test error")
        mock_get_optimizer.return_value = mock_optimizer

        # Create request
        request = ContextPreviewRequest(
            messages=[
                {"role": "user", "content": "Hello", "timestamp": "2024-01-01 10:00:00"},
            ],
            current_query="test query",
            agent_type="interaction"
        )

        # Test preview should raise HTTPException
        with pytest.raises(Exception):  # HTTPException in actual FastAPI
            await preview_context_optimization(request)

    async def test_get_sample_context_preview(self):
        """Test getting sample context preview."""
        with patch('server.routes.context_optimization.preview_context_optimization') as mock_preview:
            # Mock preview response
            mock_response = ContextPreviewResponse(
                success=True,
                original_context={"strategy": "full_context", "message_count": 10},
                optimized_context={"strategy": "smart_selection", "message_count": 5},
                comparison={"compression_ratio": 0.5}
            )
            mock_preview.return_value = mock_response

            # Test sample preview
            result = await get_sample_context_preview()

            # Verify result
            assert result["success"] is True
            assert "sample_request" in result
            assert "preview" in result
            assert result["sample_request"]["current_query"] == "Show me the most recent email from John"
            assert result["preview"]["success"] is True

    async def test_get_sample_context_preview_exception(self):
        """Test getting sample context preview with exception."""
        with patch('server.routes.context_optimization.preview_context_optimization') as mock_preview:
            mock_preview.side_effect = Exception("Test error")

            # Test sample preview should raise HTTPException
            with pytest.raises(Exception):  # HTTPException in actual FastAPI
                await get_sample_context_preview()


class TestContextOptimizationMetricsAPI:
    """Test cases for context optimization metrics API endpoints."""

    def setup_method(self):
        """Set up test fixtures."""
        reset_context_optimization_monitor()

    def teardown_method(self):
        """Clean up after tests."""
        reset_context_optimization_monitor()

    async def test_get_context_optimization_metrics_success(self):
        """Test successful metrics retrieval."""
        # Add some test data
        monitor = get_context_optimization_monitor()
        monitor.record_optimization(
            strategy="smart_selection",
            agent_type="interaction",
            original_count=10,
            optimized_count=5,
            tokens_saved=100,
            processing_time=0.1,
            compression_ratio=0.5
        )

        # Test metrics endpoint
        result = await get_context_optimization_metrics()

        # Verify result
        assert result["success"] is True
        assert "metrics" in result
        assert "performance" in result
        assert result["metrics"]["total_optimizations"] == 1
        assert result["metrics"]["avg_compression_ratio"] == 0.5

    async def test_get_context_optimization_metrics_exception(self):
        """Test metrics retrieval with exception."""
        with patch('server.routes.context_optimization.get_context_optimization_monitor') as mock_get_monitor:
            mock_get_monitor.side_effect = Exception("Test error")

            # Test metrics endpoint should raise HTTPException
            with pytest.raises(Exception):  # HTTPException in actual FastAPI
                await get_context_optimization_metrics()

    async def test_get_recent_optimizations_success(self):
        """Test successful recent optimizations retrieval."""
        # Add some test data
        monitor = get_context_optimization_monitor()
        for i in range(5):
            monitor.record_optimization(
                strategy=f"strategy_{i}",
                agent_type="interaction",
                original_count=10,
                optimized_count=5,
                tokens_saved=100,
                processing_time=0.1,
                compression_ratio=0.5
            )

        # Test recent optimizations endpoint
        result = await get_recent_optimizations(limit=3)

        # Verify result
        assert result["success"] is True
        assert "recent_optimizations" in result
        assert len(result["recent_optimizations"]) == 3
        assert result["count"] == 3

    async def test_get_recent_optimizations_exception(self):
        """Test recent optimizations retrieval with exception."""
        with patch('server.routes.context_optimization.get_context_optimization_monitor') as mock_get_monitor:
            mock_get_monitor.side_effect = Exception("Test error")

            # Test recent optimizations endpoint should raise HTTPException
            with pytest.raises(Exception):  # HTTPException in actual FastAPI
                await get_recent_optimizations(limit=5)

    async def test_reset_context_optimization_metrics_success(self):
        """Test successful metrics reset."""
        # Add some test data
        monitor = get_context_optimization_monitor()
        monitor.record_optimization(
            strategy="smart_selection",
            agent_type="interaction",
            original_count=10,
            optimized_count=5,
            tokens_saved=100,
            processing_time=0.1,
            compression_ratio=0.5
        )

        # Verify data exists
        metrics = monitor.get_metrics_summary()
        assert metrics["total_optimizations"] == 1

        # Test reset endpoint
        result = await reset_context_optimization_metrics()

        # Verify result
        assert result["success"] is True
        assert result["message"] == "Metrics reset successfully"

        # Verify data was reset
        metrics = monitor.get_metrics_summary()
        assert metrics["total_optimizations"] == 0

    async def test_reset_context_optimization_metrics_exception(self):
        """Test metrics reset with exception."""
        with patch('server.routes.context_optimization.get_context_optimization_monitor') as mock_get_monitor:
            mock_get_monitor.side_effect = Exception("Test error")

            # Test reset endpoint should raise HTTPException
            with pytest.raises(Exception):  # HTTPException in actual FastAPI
                await reset_context_optimization_metrics()

    async def test_get_context_optimization_summary_success(self):
        """Test successful summary retrieval."""
        # Add some test data
        monitor = get_context_optimization_monitor()
        for i in range(3):
            monitor.record_optimization(
                strategy="smart_selection",
                agent_type="interaction",
                original_count=10,
                optimized_count=5,
                tokens_saved=100,
                processing_time=0.1,
                compression_ratio=0.5
            )

        # Test summary endpoint
        result = await get_context_optimization_summary()

        # Verify result
        assert result["success"] is True
        assert "summary" in result
        summary = result["summary"]
        assert summary["total_optimizations"] == 3
        assert summary["efficiency_score"] > 0
        assert "strategy_distribution" in summary
        assert "agent_type_distribution" in summary
        assert "recent_optimizations" in summary

    async def test_get_context_optimization_summary_exception(self):
        """Test summary retrieval with exception."""
        with patch('server.routes.context_optimization.get_context_optimization_monitor') as mock_get_monitor:
            mock_get_monitor.side_effect = Exception("Test error")

            # Test summary endpoint should raise HTTPException
            with pytest.raises(Exception):  # HTTPException in actual FastAPI
                await get_context_optimization_summary()


class TestContextPreviewRequestModel:
    """Test cases for ContextPreviewRequest model."""

    def test_context_preview_request_validation(self):
        """Test ContextPreviewRequest model validation."""
        # Valid request
        request = ContextPreviewRequest(
            messages=[
                {"role": "user", "content": "Hello", "timestamp": "2024-01-01 10:00:00"},
                {"role": "assistant", "content": "Hi there", "timestamp": "2024-01-01 10:01:00"},
            ],
            current_query="test query",
            agent_type="interaction",
            max_tokens=1000
        )

        assert request.current_query == "test query"
        assert request.agent_type == "interaction"
        assert request.max_tokens == 1000
        assert len(request.messages) == 2

    def test_context_preview_request_defaults(self):
        """Test ContextPreviewRequest model defaults."""
        request = ContextPreviewRequest(
            messages=[
                {"role": "user", "content": "Hello", "timestamp": "2024-01-01 10:00:00"},
            ],
            current_query="test query"
        )

        assert request.agent_type == "interaction"  # Default value
        assert request.max_tokens is None  # Default value

    def test_context_preview_request_empty_messages(self):
        """Test ContextPreviewRequest with empty messages."""
        request = ContextPreviewRequest(
            messages=[],
            current_query="test query"
        )

        assert len(request.messages) == 0
        assert request.current_query == "test query"


class TestContextPreviewResponseModel:
    """Test cases for ContextPreviewResponse model."""

    def test_context_preview_response_creation(self):
        """Test ContextPreviewResponse model creation."""
        response = ContextPreviewResponse(
            success=True,
            original_context={"strategy": "full_context", "message_count": 10},
            optimized_context={"strategy": "smart_selection", "message_count": 5},
            comparison={"compression_ratio": 0.5}
        )

        assert response.success is True
        assert response.original_context["strategy"] == "full_context"
        assert response.optimized_context["strategy"] == "smart_selection"
        assert response.comparison["compression_ratio"] == 0.5

    def test_context_preview_response_dict_conversion(self):
        """Test ContextPreviewResponse dict conversion."""
        response = ContextPreviewResponse(
            success=True,
            original_context={"strategy": "full_context"},
            optimized_context={"strategy": "smart_selection"},
            comparison={"compression_ratio": 0.5}
        )

        response_dict = response.dict()
        assert response_dict["success"] is True
        assert "original_context" in response_dict
        assert "optimized_context" in response_dict
        assert "comparison" in response_dict


if __name__ == "__main__":
    pytest.main([__file__])
