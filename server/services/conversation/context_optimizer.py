"""Smart context selection for LLM performance optimization."""

from __future__ import annotations

import re
import threading
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple
from enum import Enum

from ...logging_config import logger
from ...models import ChatMessage
from ...config import get_settings
from .context_metrics import get_context_optimization_monitor


class ContextRelevanceLevel(Enum):
    """Context relevance levels for smart selection."""
    CRITICAL = "critical"  # Must include
    HIGH = "high"         # Should include
    MEDIUM = "medium"     # May include
    LOW = "low"          # Rarely include
    IRRELEVANT = "irrelevant"  # Never include


@dataclass
class ContextSegment:
    """A segment of conversation context with relevance scoring."""
    
    messages: List[ChatMessage]
    relevance_score: float
    relevance_level: ContextRelevanceLevel
    segment_type: str  # "recent", "related", "summary", "agent_history"
    start_index: int
    end_index: int
    content_length: int = field(init=False)
    
    def __post_init__(self):
        self.content_length = sum(len(msg.content) for msg in self.messages)


@dataclass
class ContextOptimizationResult:
    """Result of context optimization with selected segments."""
    
    selected_segments: List[ContextSegment]
    total_tokens_estimate: int
    optimization_strategy: str
    original_message_count: int
    optimized_message_count: int
    compression_ratio: float = field(init=False)
    
    def __post_init__(self):
        if self.original_message_count > 0:
            self.compression_ratio = self.optimized_message_count / self.original_message_count
        else:
            self.compression_ratio = 1.0


class ContextOptimizer:
    """Smart context selection for optimal LLM performance."""
    
    def __init__(self):
        self.settings = get_settings()
        self._lock = threading.RLock()
        
        # Context optimization settings from config
        self.max_context_tokens = self.settings.context_max_tokens
        self.recent_messages_count = self.settings.context_recent_messages_count
        self.min_relevance_threshold = self.settings.context_min_relevance_threshold
        self.optimization_enabled = self.settings.context_optimization_enabled
        self.compression_enabled = self.settings.context_compression_enabled
        
        logger.info(
            "context optimizer initialized",
            extra={
                "optimization_enabled": self.optimization_enabled,
                "max_context_tokens": self.max_context_tokens,
                "recent_messages_count": self.recent_messages_count,
                "min_relevance_threshold": self.min_relevance_threshold,
                "compression_enabled": self.compression_enabled,
            }
        )
    
    def optimize_context(
        self,
        messages: List[ChatMessage],
        current_query: str,
        agent_type: str = "interaction",
        max_tokens: Optional[int] = None
    ) -> ContextOptimizationResult:
        """
        Optimize context for LLM consumption.
        
        Args:
            messages: Full conversation messages
            current_query: Current user query or instruction
            agent_type: Type of agent ("interaction" or "execution")
            max_tokens: Maximum tokens to use (overrides default)
            
        Returns:
            Optimized context result
        """
        import time
        start_time = time.time()
        
        logger.info(
            "🚀 CONTEXT OPTIMIZATION STARTED",
            extra={
                "agent_type": agent_type,
                "original_messages": len(messages),
                "current_query_length": len(current_query),
                "max_tokens": max_tokens or self.max_context_tokens,
                "optimization_enabled": self.optimization_enabled,
            }
        )
        
        with self._lock:
            if not messages:
                result = ContextOptimizationResult(
                    selected_segments=[],
                    total_tokens_estimate=0,
                    optimization_strategy="empty",
                    original_message_count=0,
                    optimized_message_count=0,
                )
                self._record_optimization_metrics(result, agent_type, start_time)
                return result
            
            # If optimization is disabled, return full context
            if not self.optimization_enabled:
                result = self._optimize_full_context(messages, current_query, max_tokens)
                self._record_optimization_metrics(result, agent_type, start_time)
                return result
            
            # Determine optimization strategy based on context size
            strategy = self._determine_strategy(messages, current_query, agent_type)
            
            logger.info(
                "🎯 OPTIMIZATION STRATEGY SELECTED",
                extra={
                    "strategy": strategy,
                    "message_count": len(messages),
                    "estimated_tokens": self._estimate_tokens(messages),
                    "agent_type": agent_type,
                }
            )
            
            # Apply optimization strategy
            if strategy == "recent_only":
                result = self._optimize_recent_only(messages, current_query, max_tokens)
            elif strategy == "smart_selection":
                result = self._optimize_smart_selection(messages, current_query, agent_type, max_tokens)
            elif strategy == "full_context":
                result = self._optimize_full_context(messages, current_query, max_tokens)
            else:
                # Fallback to recent only
                result = self._optimize_recent_only(messages, current_query, max_tokens)
            
            # Record metrics
            self._record_optimization_metrics(result, agent_type, start_time)
            
            processing_time = time.time() - start_time
            logger.info(
                "✅ CONTEXT OPTIMIZATION COMPLETED",
                extra={
                    "strategy": result.optimization_strategy,
                    "original_messages": result.original_message_count,
                    "optimized_messages": result.optimized_message_count,
                    "compression_ratio": result.compression_ratio,
                    "tokens_estimate": result.total_tokens_estimate,
                    "segments_selected": len(result.selected_segments),
                    "processing_time_ms": round(processing_time * 1000, 2),
                    "agent_type": agent_type,
                }
            )
            
            return result
    
    def _determine_strategy(
        self,
        messages: List[ChatMessage],
        current_query: str,
        agent_type: str
    ) -> str:
        """Determine the best optimization strategy."""
        message_count = len(messages)
        estimated_tokens = self._estimate_tokens(messages)
        
        # Simple heuristics for strategy selection
        if message_count <= 20:
            return "full_context"
        elif estimated_tokens <= self.max_context_tokens * 0.7:
            return "smart_selection"
        else:
            return "recent_only"
    
    def _optimize_recent_only(
        self,
        messages: List[ChatMessage],
        current_query: str,
        max_tokens: Optional[int]
    ) -> ContextOptimizationResult:
        """Optimize by keeping only recent messages."""
        recent_count = min(self.recent_messages_count, len(messages))
        recent_messages = messages[-recent_count:] if recent_count > 0 else []
        
        segment = ContextSegment(
            messages=recent_messages,
            relevance_score=1.0,
            relevance_level=ContextRelevanceLevel.CRITICAL,
            segment_type="recent",
            start_index=max(0, len(messages) - recent_count),
            end_index=len(messages) - 1,
        )
        
        return ContextOptimizationResult(
            selected_segments=[segment],
            total_tokens_estimate=self._estimate_tokens(recent_messages),
            optimization_strategy="recent_only",
            original_message_count=len(messages),
            optimized_message_count=len(recent_messages),
        )
    
    def _optimize_smart_selection(
        self,
        messages: List[ChatMessage],
        current_query: str,
        agent_type: str,
        max_tokens: Optional[int]
    ) -> ContextOptimizationResult:
        """Optimize using smart relevance-based selection."""
        segments = self._create_context_segments(messages, current_query, agent_type)
        
        logger.info(
            "🔍 SMART SELECTION: SEGMENTS CREATED",
            extra={
                "total_segments": len(segments),
                "agent_type": agent_type,
                "query_length": len(current_query),
            }
        )
        
        # Score and filter segments
        scored_segments = []
        for segment in segments:
            relevance_score = self._calculate_relevance_score(segment, current_query, agent_type)
            segment.relevance_score = relevance_score
            segment.relevance_level = self._score_to_level(relevance_score)
            scored_segments.append(segment)
            
            logger.debug(
                "📊 SEGMENT SCORED",
                extra={
                    "segment_type": segment.segment_type,
                    "relevance_score": round(relevance_score, 3),
                    "relevance_level": segment.relevance_level.value,
                    "messages_count": len(segment.messages),
                    "content_length": segment.content_length,
                }
            )
        
        # Sort by relevance score (descending)
        scored_segments.sort(key=lambda s: s.relevance_score, reverse=True)
        
        # Select segments within token limit
        selected_segments = []
        total_tokens = 0
        token_limit = max_tokens or self.max_context_tokens
        
        logger.info(
            "🎯 SMART SELECTION: SELECTING SEGMENTS",
            extra={
                "token_limit": token_limit,
                "min_relevance_threshold": self.min_relevance_threshold,
                "scored_segments": len(scored_segments),
            }
        )
        
        for segment in scored_segments:
            segment_tokens = self._estimate_tokens(segment.messages)
            
            # Always include critical segments
            if segment.relevance_level == ContextRelevanceLevel.CRITICAL:
                selected_segments.append(segment)
                total_tokens += segment_tokens
                logger.info(
                    "⭐ CRITICAL SEGMENT SELECTED",
                    extra={
                        "segment_type": segment.segment_type,
                        "relevance_score": round(segment.relevance_score, 3),
                        "tokens": segment_tokens,
                        "total_tokens": total_tokens,
                    }
                )
            # Include high/medium relevance segments if we have space
            elif (segment.relevance_score >= self.min_relevance_threshold and 
                  total_tokens + segment_tokens <= token_limit):
                selected_segments.append(segment)
                total_tokens += segment_tokens
                logger.info(
                    "✅ RELEVANT SEGMENT SELECTED",
                    extra={
                        "segment_type": segment.segment_type,
                        "relevance_score": round(segment.relevance_score, 3),
                        "tokens": segment_tokens,
                        "total_tokens": total_tokens,
                    }
                )
            # Stop if we're approaching the limit
            elif total_tokens > token_limit * 0.8:
                logger.info(
                    "⏹️ SEGMENT SELECTION STOPPED",
                    extra={
                        "reason": "approaching_token_limit",
                        "total_tokens": total_tokens,
                        "token_limit": token_limit,
                        "remaining_segments": len(scored_segments) - len(selected_segments),
                    }
                )
                break
            else:
                logger.debug(
                    "❌ SEGMENT REJECTED",
                    extra={
                        "segment_type": segment.segment_type,
                        "relevance_score": round(segment.relevance_score, 3),
                        "reason": "below_threshold_or_over_limit",
                        "min_threshold": self.min_relevance_threshold,
                    }
                )
        
        # Sort selected segments by original order
        selected_segments.sort(key=lambda s: s.start_index)
        
        return ContextOptimizationResult(
            selected_segments=selected_segments,
            total_tokens_estimate=total_tokens,
            optimization_strategy="smart_selection",
            original_message_count=len(messages),
            optimized_message_count=sum(len(s.messages) for s in selected_segments),
        )
    
    def _optimize_full_context(
        self,
        messages: List[ChatMessage],
        current_query: str,
        max_tokens: Optional[int]
    ) -> ContextOptimizationResult:
        """Use full context (no optimization needed)."""
        segment = ContextSegment(
            messages=messages,
            relevance_score=1.0,
            relevance_level=ContextRelevanceLevel.CRITICAL,
            segment_type="full",
            start_index=0,
            end_index=len(messages) - 1,
        )
        
        return ContextOptimizationResult(
            selected_segments=[segment],
            total_tokens_estimate=self._estimate_tokens(messages),
            optimization_strategy="full_context",
            original_message_count=len(messages),
            optimized_message_count=len(messages),
        )
    
    def _create_context_segments(
        self,
        messages: List[ChatMessage],
        current_query: str,
        agent_type: str
    ) -> List[ContextSegment]:
        """Create logical segments from conversation messages."""
        segments = []
        
        if not messages:
            return segments
        
        # Recent messages segment (always high priority)
        recent_count = min(self.recent_messages_count, len(messages))
        if recent_count > 0:
            recent_messages = messages[-recent_count:]
            segments.append(ContextSegment(
                messages=recent_messages,
                relevance_score=0.0,  # Will be calculated later
                relevance_level=ContextRelevanceLevel.HIGH,
                segment_type="recent",
                start_index=len(messages) - recent_count,
                end_index=len(messages) - 1,
            ))
        
        # Create additional segments for older messages
        if len(messages) > recent_count:
            # Group older messages into chunks
            chunk_size = 10
            older_messages = messages[:-recent_count] if recent_count > 0 else messages
            
            for i in range(0, len(older_messages), chunk_size):
                chunk_messages = older_messages[i:i + chunk_size]
                segments.append(ContextSegment(
                    messages=chunk_messages,
                    relevance_score=0.0,  # Will be calculated later
                    relevance_level=ContextRelevanceLevel.MEDIUM,
                    segment_type="historical",
                    start_index=i,
                    end_index=i + len(chunk_messages) - 1,
                ))
        
        return segments
    
    def _calculate_relevance_score(
        self,
        segment: ContextSegment,
        current_query: str,
        agent_type: str
    ) -> float:
        """Calculate relevance score for a context segment."""
        if not segment.messages:
            return 0.0
        
        # Base score from segment type
        base_scores = {
            "recent": 0.9,
            "historical": 0.3,
            "summary": 0.7,
            "agent_history": 0.5,
        }
        base_score = base_scores.get(segment.segment_type, 0.3)
        
        # Boost score based on content similarity
        content_similarity = self._calculate_content_similarity(segment, current_query)
        
        # Boost score for agent-specific relevance
        agent_relevance = self._calculate_agent_relevance(segment, agent_type)
        
        # Combine scores with weights
        final_score = (
            base_score * 0.4 +
            content_similarity * 0.4 +
            agent_relevance * 0.2
        )
        
        return min(1.0, max(0.0, final_score))
    
    def _calculate_content_similarity(
        self,
        segment: ContextSegment,
        current_query: str
    ) -> float:
        """Calculate content similarity between segment and current query."""
        if not segment.messages or not current_query:
            return 0.0
        
        # Simple keyword-based similarity
        query_words = set(re.findall(r'\b\w+\b', current_query.lower()))
        
        total_similarity = 0.0
        for message in segment.messages:
            message_words = set(re.findall(r'\b\w+\b', message.content.lower()))
            
            if query_words and message_words:
                # Calculate Jaccard similarity
                intersection = len(query_words.intersection(message_words))
                union = len(query_words.union(message_words))
                similarity = intersection / union if union > 0 else 0.0
                total_similarity += similarity
        
        return total_similarity / len(segment.messages) if segment.messages else 0.0
    
    def _calculate_agent_relevance(
        self,
        segment: ContextSegment,
        agent_type: str
    ) -> float:
        """Calculate agent-specific relevance score."""
        if not segment.messages:
            return 0.0
        
        # Agent-specific keywords and patterns
        agent_patterns = {
            "interaction": [
                r"\b(user|poke|assistant|help|question|request)\b",
                r"\b(email|message|send|draft)\b",
                r"\b(search|find|look)\b",
            ],
            "execution": [
                r"\b(execute|run|perform|complete|task)\b",
                r"\b(email|gmail|search|draft|send)\b",
                r"\b(agent|tool|function)\b",
            ],
        }
        
        patterns = agent_patterns.get(agent_type, [])
        if not patterns:
            return 0.5  # Neutral score
        
        total_relevance = 0.0
        for message in segment.messages:
            message_relevance = 0.0
            for pattern in patterns:
                matches = len(re.findall(pattern, message.content.lower()))
                message_relevance += matches * 0.1
            
            total_relevance += min(1.0, message_relevance)
        
        return total_relevance / len(segment.messages) if segment.messages else 0.0
    
    def _score_to_level(self, score: float) -> ContextRelevanceLevel:
        """Convert numeric score to relevance level."""
        if score >= 0.8:
            return ContextRelevanceLevel.CRITICAL
        elif score >= 0.6:
            return ContextRelevanceLevel.HIGH
        elif score >= 0.4:
            return ContextRelevanceLevel.MEDIUM
        elif score >= 0.2:
            return ContextRelevanceLevel.LOW
        else:
            return ContextRelevanceLevel.IRRELEVANT
    
    def _estimate_tokens(self, messages: List[ChatMessage]) -> int:
        """Estimate token count for messages."""
        if not messages:
            return 0
        
        # Rough estimation: 1 token ≈ 4 characters
        total_chars = sum(len(msg.content) for msg in messages)
        return int(total_chars / 4)
    
    def get_optimization_stats(self) -> Dict[str, any]:
        """Get context optimization statistics."""
        return {
            "max_context_tokens": self.max_context_tokens,
            "recent_messages_count": self.recent_messages_count,
            "min_relevance_threshold": self.min_relevance_threshold,
            "optimization_strategies": ["recent_only", "smart_selection", "full_context"],
        }

    def _record_optimization_metrics(
        self,
        result: ContextOptimizationResult,
        agent_type: str,
        start_time: float
    ) -> None:
        """Record optimization metrics."""
        try:
            processing_time = time.time() - start_time
            tokens_saved = result.total_tokens_estimate - (result.total_tokens_estimate * result.compression_ratio)
            
            monitor = get_context_optimization_monitor()
            monitor.record_optimization(
                strategy=result.optimization_strategy,
                agent_type=agent_type,
                original_count=result.original_message_count,
                optimized_count=result.optimized_message_count,
                tokens_saved=int(tokens_saved),
                processing_time=processing_time,
                compression_ratio=result.compression_ratio
            )
        except Exception as exc:
            logger.warning(
                "failed to record context optimization metrics",
                extra={"error": str(exc)}
            )


# Global context optimizer instance
_context_optimizer: Optional[ContextOptimizer] = None
_optimizer_lock = threading.Lock()


def get_context_optimizer() -> ContextOptimizer:
    """Get global context optimizer instance."""
    global _context_optimizer
    if _context_optimizer is None:
        with _optimizer_lock:
            if _context_optimizer is None:
                _context_optimizer = ContextOptimizer()
    return _context_optimizer


def reset_context_optimizer() -> None:
    """Reset global context optimizer (for testing)."""
    global _context_optimizer
    with _optimizer_lock:
        _context_optimizer = None


__all__ = [
    "ContextOptimizer",
    "ContextOptimizationResult", 
    "ContextSegment",
    "ContextRelevanceLevel",
    "get_context_optimizer",
    "reset_context_optimizer",
]
