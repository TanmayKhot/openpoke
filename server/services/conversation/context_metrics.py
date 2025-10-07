"""Context optimization metrics and monitoring."""

from __future__ import annotations

import threading
import time
from collections import defaultdict, deque
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from ...logging_config import logger


@dataclass
class ContextOptimizationMetrics:
    """Metrics for context optimization performance."""
    
    total_optimizations: int = 0
    total_original_messages: int = 0
    total_optimized_messages: int = 0
    total_tokens_saved: int = 0
    strategy_counts: Dict[str, int] = field(default_factory=dict)
    agent_type_counts: Dict[str, int] = field(default_factory=dict)
    compression_ratios: List[float] = field(default_factory=list)
    processing_times: List[float] = field(default_factory=list)
    last_updated: float = field(default_factory=time.time)


class ContextOptimizationMonitor:
    """Monitor and track context optimization performance."""
    
    def __init__(self, max_history: int = 1000):
        self.max_history = max_history
        self._lock = threading.RLock()
        self._metrics = ContextOptimizationMetrics()
        self._recent_optimizations = deque(maxlen=max_history)
        
        logger.info("context optimization monitor initialized")
    
    def record_optimization(
        self,
        strategy: str,
        agent_type: str,
        original_count: int,
        optimized_count: int,
        tokens_saved: int,
        processing_time: float,
        compression_ratio: float
    ) -> None:
        """Record a context optimization event."""
        with self._lock:
            # Update metrics
            self._metrics.total_optimizations += 1
            self._metrics.total_original_messages += original_count
            self._metrics.total_optimized_messages += optimized_count
            self._metrics.total_tokens_saved += tokens_saved
            
            # Update strategy counts
            self._metrics.strategy_counts[strategy] = self._metrics.strategy_counts.get(strategy, 0) + 1
            
            # Update agent type counts
            self._metrics.agent_type_counts[agent_type] = self._metrics.agent_type_counts.get(agent_type, 0) + 1
            
            # Update lists (with size limits)
            self._metrics.compression_ratios.append(compression_ratio)
            if len(self._metrics.compression_ratios) > self.max_history:
                self._metrics.compression_ratios.pop(0)
            
            self._metrics.processing_times.append(processing_time)
            if len(self._metrics.processing_times) > self.max_history:
                self._metrics.processing_times.pop(0)
            
            self._metrics.last_updated = time.time()
            
            # Store recent optimization details
            optimization_record = {
                "timestamp": time.time(),
                "strategy": strategy,
                "agent_type": agent_type,
                "original_count": original_count,
                "optimized_count": optimized_count,
                "tokens_saved": tokens_saved,
                "processing_time": processing_time,
                "compression_ratio": compression_ratio,
            }
            self._recent_optimizations.append(optimization_record)
            
            # Log optimization event
            logger.info(
                "context optimization recorded",
                extra={
                    "strategy": strategy,
                    "agent_type": agent_type,
                    "original_messages": original_count,
                    "optimized_messages": optimized_count,
                    "compression_ratio": compression_ratio,
                    "tokens_saved": tokens_saved,
                    "processing_time_ms": processing_time * 1000,
                }
            )
    
    def get_metrics_summary(self) -> Dict[str, any]:
        """Get summary of context optimization metrics."""
        with self._lock:
            if not self._metrics.compression_ratios:
                avg_compression_ratio = 1.0
                avg_processing_time = 0.0
            else:
                avg_compression_ratio = sum(self._metrics.compression_ratios) / len(self._metrics.compression_ratios)
                avg_processing_time = sum(self._metrics.processing_times) / len(self._metrics.processing_times)
            
            return {
                "total_optimizations": self._metrics.total_optimizations,
                "total_original_messages": self._metrics.total_original_messages,
                "total_optimized_messages": self._metrics.total_optimized_messages,
                "total_tokens_saved": self._metrics.total_tokens_saved,
                "avg_compression_ratio": avg_compression_ratio,
                "avg_processing_time_ms": avg_processing_time * 1000,
                "strategy_distribution": dict(self._metrics.strategy_counts),
                "agent_type_distribution": dict(self._metrics.agent_type_counts),
                "last_updated": self._metrics.last_updated,
                "recent_optimizations_count": len(self._recent_optimizations),
            }
    
    def get_performance_stats(self) -> Dict[str, any]:
        """Get detailed performance statistics."""
        with self._lock:
            if not self._metrics.compression_ratios:
                return {
                    "compression_stats": {"min": 1.0, "max": 1.0, "avg": 1.0, "median": 1.0},
                    "processing_stats": {"min": 0.0, "max": 0.0, "avg": 0.0, "median": 0.0},
                }
            
            # Calculate compression ratio statistics
            compression_ratios = sorted(self._metrics.compression_ratios)
            compression_stats = {
                "min": compression_ratios[0],
                "max": compression_ratios[-1],
                "avg": sum(compression_ratios) / len(compression_ratios),
                "median": compression_ratios[len(compression_ratios) // 2],
            }
            
            # Calculate processing time statistics
            processing_times = sorted(self._metrics.processing_times)
            processing_stats = {
                "min": processing_times[0] * 1000,  # Convert to ms
                "max": processing_times[-1] * 1000,
                "avg": (sum(processing_times) / len(processing_times)) * 1000,
                "median": processing_times[len(processing_times) // 2] * 1000,
            }
            
            return {
                "compression_stats": compression_stats,
                "processing_stats": processing_stats,
            }
    
    def get_recent_optimizations(self, limit: int = 10) -> List[Dict[str, any]]:
        """Get recent optimization records."""
        with self._lock:
            recent = list(self._recent_optimizations)[-limit:]
            return [
                {
                    "timestamp": record["timestamp"],
                    "strategy": record["strategy"],
                    "agent_type": record["agent_type"],
                    "original_count": record["original_count"],
                    "optimized_count": record["optimized_count"],
                    "compression_ratio": record["compression_ratio"],
                    "tokens_saved": record["tokens_saved"],
                    "processing_time_ms": record["processing_time"] * 1000,
                }
                for record in recent
            ]
    
    def reset_metrics(self) -> None:
        """Reset all metrics (for testing)."""
        with self._lock:
            self._metrics = ContextOptimizationMetrics()
            self._recent_optimizations.clear()
            logger.info("context optimization metrics reset")
    
    def log_performance_summary(self) -> None:
        """Log a performance summary."""
        summary = self.get_metrics_summary()
        performance = self.get_performance_stats()
        
        logger.info(
            "context optimization performance summary",
            extra={
                **summary,
                **performance,
            }
        )


# Global monitor instance
_context_monitor: Optional[ContextOptimizationMonitor] = None
_monitor_lock = threading.Lock()


def get_context_optimization_monitor() -> ContextOptimizationMonitor:
    """Get global context optimization monitor instance."""
    global _context_monitor
    if _context_monitor is None:
        with _monitor_lock:
            if _context_monitor is None:
                _context_monitor = ContextOptimizationMonitor()
    return _context_monitor


def reset_context_optimization_monitor() -> None:
    """Reset global context optimization monitor (for testing)."""
    global _context_monitor
    with _monitor_lock:
        _context_monitor = None


# Context optimization decorator for automatic metrics collection
def track_context_optimization(agent_type: str = "unknown"):
    """Decorator to automatically track context optimization metrics."""
    def decorator(func):
        def wrapper(*args, **kwargs):
            start_time = time.time()
            
            try:
                result = func(*args, **kwargs)
                
                # Calculate metrics
                processing_time = time.time() - start_time
                original_count = result.original_message_count
                optimized_count = result.optimized_message_count
                compression_ratio = result.compression_ratio
                tokens_saved = result.total_tokens_estimate - (result.total_tokens_estimate * compression_ratio)
                
                # Record metrics
                monitor = get_context_optimization_monitor()
                monitor.record_optimization(
                    strategy=result.optimization_strategy,
                    agent_type=agent_type,
                    original_count=original_count,
                    optimized_count=optimized_count,
                    tokens_saved=int(tokens_saved),
                    processing_time=processing_time,
                    compression_ratio=compression_ratio
                )
                
                return result
                
            except Exception as exc:
                logger.error(
                    "context optimization failed",
                    extra={
                        "agent_type": agent_type,
                        "error": str(exc),
                        "processing_time_ms": (time.time() - start_time) * 1000,
                    }
                )
                raise
        
        return wrapper
    return decorator


__all__ = [
    "ContextOptimizationMonitor",
    "ContextOptimizationMetrics",
    "get_context_optimization_monitor",
    "reset_context_optimization_monitor",
    "track_context_optimization",
]
