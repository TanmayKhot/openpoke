"""Unit tests for context optimization metrics and monitoring."""

import pytest
import time
from unittest.mock import Mock, patch
from typing import Dict, List

from server.services.conversation.context_metrics import (
    ContextOptimizationMonitor,
    ContextOptimizationMetrics,
    get_context_optimization_monitor,
    reset_context_optimization_monitor,
    track_context_optimization,
)
from server.services.conversation.context_optimizer import ContextOptimizationResult


class TestContextOptimizationMetrics:
    """Test cases for ContextOptimizationMetrics class."""

    def test_metrics_initialization(self):
        """Test metrics initialization with default values."""
        metrics = ContextOptimizationMetrics()
        
        assert metrics.total_optimizations == 0
        assert metrics.total_original_messages == 0
        assert metrics.total_optimized_messages == 0
        assert metrics.total_tokens_saved == 0
        assert metrics.strategy_counts == {}
        assert metrics.agent_type_counts == {}
        assert metrics.compression_ratios == []
        assert metrics.processing_times == []
        assert metrics.last_updated > 0

    def test_metrics_with_data(self):
        """Test metrics with sample data."""
        metrics = ContextOptimizationMetrics()
        metrics.total_optimizations = 10
        metrics.total_original_messages = 100
        metrics.total_optimized_messages = 50
        metrics.total_tokens_saved = 5000
        metrics.strategy_counts = {"smart_selection": 5, "recent_only": 3, "full_context": 2}
        metrics.agent_type_counts = {"interaction": 7, "execution": 3}
        metrics.compression_ratios = [0.5, 0.6, 0.7]
        metrics.processing_times = [0.1, 0.2, 0.15]
        
        assert metrics.total_optimizations == 10
        assert metrics.strategy_counts["smart_selection"] == 5
        assert len(metrics.compression_ratios) == 3


class TestContextOptimizationMonitor:
    """Test cases for ContextOptimizationMonitor class."""

    def setup_method(self):
        """Set up test fixtures."""
        self.monitor = ContextOptimizationMonitor(max_history=10)

    def test_monitor_initialization(self):
        """Test monitor initialization."""
        assert self.monitor.max_history == 10
        assert len(self.monitor._metrics.compression_ratios) == 0
        assert len(self.monitor._recent_optimizations) == 0

    def test_record_optimization(self):
        """Test recording optimization metrics."""
        self.monitor.record_optimization(
            strategy="smart_selection",
            agent_type="interaction",
            original_count=20,
            optimized_count=10,
            tokens_saved=1000,
            processing_time=0.1,
            compression_ratio=0.5
        )
        
        assert self.monitor._metrics.total_optimizations == 1
        assert self.monitor._metrics.total_original_messages == 20
        assert self.monitor._metrics.total_optimized_messages == 10
        assert self.monitor._metrics.total_tokens_saved == 1000
        assert self.monitor._metrics.strategy_counts["smart_selection"] == 1
        assert self.monitor._metrics.agent_type_counts["interaction"] == 1
        assert len(self.monitor._metrics.compression_ratios) == 1
        assert len(self.monitor._metrics.processing_times) == 1
        assert len(self.monitor._recent_optimizations) == 1

    def test_record_multiple_optimizations(self):
        """Test recording multiple optimizations."""
        for i in range(5):
            self.monitor.record_optimization(
                strategy="smart_selection",
                agent_type="interaction",
                original_count=10,
                optimized_count=5,
                tokens_saved=500,
                processing_time=0.1,
                compression_ratio=0.5
            )
        
        assert self.monitor._metrics.total_optimizations == 5
        assert self.monitor._metrics.strategy_counts["smart_selection"] == 5
        assert len(self.monitor._metrics.compression_ratios) == 5

    def test_get_metrics_summary(self):
        """Test getting metrics summary."""
        # Record some test data
        self.monitor.record_optimization(
            strategy="smart_selection",
            agent_type="interaction",
            original_count=20,
            optimized_count=10,
            tokens_saved=1000,
            processing_time=0.1,
            compression_ratio=0.5
        )
        
        summary = self.monitor.get_metrics_summary()
        
        assert summary["total_optimizations"] == 1
        assert summary["total_original_messages"] == 20
        assert summary["total_optimized_messages"] == 10
        assert summary["total_tokens_saved"] == 1000
        assert summary["avg_compression_ratio"] == 0.5
        assert summary["avg_processing_time_ms"] == 100.0  # 0.1 * 1000
        assert summary["strategy_distribution"]["smart_selection"] == 1
        assert summary["agent_type_distribution"]["interaction"] == 1

    def test_get_metrics_summary_empty(self):
        """Test getting metrics summary with no data."""
        summary = self.monitor.get_metrics_summary()
        
        assert summary["total_optimizations"] == 0
        assert summary["avg_compression_ratio"] == 1.0
        assert summary["avg_processing_time_ms"] == 0.0

    def test_get_performance_stats(self):
        """Test getting performance statistics."""
        # Record test data with known values
        compression_ratios = [0.3, 0.5, 0.7, 0.9]
        processing_times = [0.05, 0.1, 0.15, 0.2]
        
        for ratio, proc_time in zip(compression_ratios, processing_times):
            self.monitor.record_optimization(
                strategy="smart_selection",
                agent_type="interaction",
                original_count=10,
                optimized_count=int(10 * ratio),
                tokens_saved=100,
                processing_time=proc_time,
                compression_ratio=ratio
            )
        
        stats = self.monitor.get_performance_stats()
        
        # Check compression stats
        assert stats["compression_stats"]["min"] == 0.3
        assert stats["compression_stats"]["max"] == 0.9
        assert stats["compression_stats"]["avg"] == 0.6
        assert stats["compression_stats"]["median"] == 0.6
        
        # Check processing stats (converted to ms)
        assert stats["processing_stats"]["min"] == 50.0
        assert stats["processing_stats"]["max"] == 200.0
        assert stats["processing_stats"]["avg"] == 125.0
        assert stats["processing_stats"]["median"] == 125.0

    def test_get_performance_stats_empty(self):
        """Test getting performance stats with no data."""
        stats = self.monitor.get_performance_stats()
        
        assert stats["compression_stats"]["min"] == 1.0
        assert stats["compression_stats"]["max"] == 1.0
        assert stats["compression_stats"]["avg"] == 1.0
        assert stats["compression_stats"]["median"] == 1.0

    def test_get_recent_optimizations(self):
        """Test getting recent optimization records."""
        # Record multiple optimizations
        for i in range(5):
            self.monitor.record_optimization(
                strategy=f"strategy_{i}",
                agent_type="interaction",
                original_count=10,
                optimized_count=5,
                tokens_saved=100,
                processing_time=0.1,
                compression_ratio=0.5
            )
        
        recent = self.monitor.get_recent_optimizations(limit=3)
        
        assert len(recent) == 3
        assert recent[0]["strategy"] == "strategy_2"  # Most recent
        assert recent[1]["strategy"] == "strategy_3"
        assert recent[2]["strategy"] == "strategy_4"
        
        # Check record structure
        record = recent[0]
        assert "timestamp" in record
        assert "strategy" in record
        assert "agent_type" in record
        assert "original_count" in record
        assert "optimized_count" in record
        assert "compression_ratio" in record
        assert "tokens_saved" in record
        assert "processing_time_ms" in record

    def test_reset_metrics(self):
        """Test resetting metrics."""
        # Record some data
        self.monitor.record_optimization(
            strategy="smart_selection",
            agent_type="interaction",
            original_count=10,
            optimized_count=5,
            tokens_saved=100,
            processing_time=0.1,
            compression_ratio=0.5
        )
        
        # Verify data exists
        assert self.monitor._metrics.total_optimizations == 1
        assert len(self.monitor._recent_optimizations) == 1
        
        # Reset
        self.monitor.reset_metrics()
        
        # Verify reset
        assert self.monitor._metrics.total_optimizations == 0
        assert len(self.monitor._recent_optimizations) == 0

    def test_max_history_limit(self):
        """Test max history limit enforcement."""
        monitor = ContextOptimizationMonitor(max_history=3)
        
        # Record more than max_history
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
        
        # Should only keep the most recent 3
        assert len(monitor._recent_optimizations) == 3
        assert len(monitor._metrics.compression_ratios) == 3
        assert len(monitor._metrics.processing_times) == 3

    def test_log_performance_summary(self):
        """Test logging performance summary."""
        # Record some data
        self.monitor.record_optimization(
            strategy="smart_selection",
            agent_type="interaction",
            original_count=10,
            optimized_count=5,
            tokens_saved=100,
            processing_time=0.1,
            compression_ratio=0.5
        )
        
        # Should not raise exception
        self.monitor.log_performance_summary()


class TestGlobalMonitor:
    """Test cases for global monitor functions."""

    def test_get_context_optimization_monitor(self):
        """Test getting global monitor instance."""
        monitor1 = get_context_optimization_monitor()
        monitor2 = get_context_optimization_monitor()
        
        # Should return the same instance
        assert monitor1 is monitor2
        assert isinstance(monitor1, ContextOptimizationMonitor)

    def test_reset_context_optimization_monitor(self):
        """Test resetting global monitor."""
        monitor1 = get_context_optimization_monitor()
        reset_context_optimization_monitor()
        monitor2 = get_context_optimization_monitor()
        
        # Should return different instances after reset
        assert monitor1 is not monitor2


class TestTrackContextOptimizationDecorator:
    """Test cases for the track_context_optimization decorator."""

    def test_decorator_success(self):
        """Test decorator with successful optimization."""
        @track_context_optimization(agent_type="test")
        def mock_optimize():
            return ContextOptimizationResult(
                selected_segments=[],
                total_tokens_estimate=1000,
                optimization_strategy="test",
                original_message_count=10,
                optimized_message_count=5
            )
        
        result = mock_optimize()
        
        # Check that metrics were recorded
        monitor = get_context_optimization_monitor()
        summary = monitor.get_metrics_summary()
        
        assert summary["total_optimizations"] == 1
        assert summary["agent_type_distribution"]["test"] == 1
        assert result.optimization_strategy == "test"

    def test_decorator_exception(self):
        """Test decorator with exception."""
        @track_context_optimization(agent_type="test")
        def mock_optimize_fail():
            raise ValueError("Test error")
        
        with pytest.raises(ValueError, match="Test error"):
            mock_optimize_fail()
        
        # Should not record metrics on failure
        monitor = get_context_optimization_monitor()
        summary = monitor.get_metrics_summary()
        assert summary["total_optimizations"] == 0

    def test_decorator_with_args(self):
        """Test decorator with function arguments."""
        @track_context_optimization(agent_type="interaction")
        def mock_optimize_with_args(messages, query):
            return ContextOptimizationResult(
                selected_segments=[],
                total_tokens_estimate=500,
                optimization_strategy="smart_selection",
                original_message_count=len(messages),
                optimized_message_count=len(messages) // 2
            )
        
        messages = ["msg1", "msg2", "msg3", "msg4"]
        result = mock_optimize_with_args(messages, "test query")
        
        assert result.original_message_count == 4
        assert result.optimized_message_count == 2


if __name__ == "__main__":
    pytest.main([__file__])
