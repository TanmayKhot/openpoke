"""Context optimization metrics API endpoint."""

from fastapi import APIRouter, HTTPException, Query
from typing import Dict, Any, Optional, List
from pydantic import BaseModel

from server.services.conversation.context_optimizer import get_context_optimizer
from server.services.conversation.context_metrics import get_context_optimization_monitor
from server.models import ChatMessage
from server.logging_config import logger

router = APIRouter()


class ContextPreviewRequest(BaseModel):
    """Request model for context preview."""
    messages: List[Dict[str, str]]
    current_query: str
    agent_type: str = "interaction"
    max_tokens: Optional[int] = None


class ContextPreviewResponse(BaseModel):
    """Response model for context preview."""
    success: bool
    original_context: Dict[str, Any]
    optimized_context: Dict[str, Any]
    comparison: Dict[str, Any]


@router.get("/context-optimization/metrics")
async def get_context_optimization_metrics() -> Dict[str, Any]:
    """Get context optimization performance metrics."""
    try:
        monitor = get_context_optimization_monitor()
        metrics = monitor.get_metrics_summary()
        performance = monitor.get_performance_stats()
        
        return {
            "success": True,
            "metrics": metrics,
            "performance": performance,
        }
    except Exception as exc:
        logger.error("failed to get context optimization metrics", extra={"error": str(exc)})
        raise HTTPException(status_code=500, detail="Failed to retrieve metrics")


@router.get("/context-optimization/recent")
async def get_recent_optimizations(limit: int = 10) -> Dict[str, Any]:
    """Get recent context optimization records."""
    try:
        monitor = get_context_optimization_monitor()
        recent = monitor.get_recent_optimizations(limit)
        
        return {
            "success": True,
            "recent_optimizations": recent,
            "count": len(recent),
        }
    except Exception as exc:
        logger.error("failed to get recent optimizations", extra={"error": str(exc)})
        raise HTTPException(status_code=500, detail="Failed to retrieve recent optimizations")


@router.post("/context-optimization/reset")
async def reset_context_optimization_metrics() -> Dict[str, Any]:
    """Reset context optimization metrics (for testing)."""
    try:
        monitor = get_context_optimization_monitor()
        monitor.reset_metrics()
        
        logger.info("context optimization metrics reset via API")
        
        return {
            "success": True,
            "message": "Metrics reset successfully",
        }
    except Exception as exc:
        logger.error("failed to reset context optimization metrics", extra={"error": str(exc)})
        raise HTTPException(status_code=500, detail="Failed to reset metrics")


@router.get("/context-optimization/summary")
async def get_context_optimization_summary() -> Dict[str, Any]:
    """Get a comprehensive context optimization summary."""
    try:
        monitor = get_context_optimization_monitor()
        
        # Get all metrics
        metrics = monitor.get_metrics_summary()
        performance = monitor.get_performance_stats()
        recent = monitor.get_recent_optimizations(5)
        
        # Calculate efficiency metrics
        total_optimizations = metrics["total_optimizations"]
        if total_optimizations > 0:
            avg_compression = metrics["avg_compression_ratio"]
            avg_processing_time = metrics["avg_processing_time_ms"]
            total_tokens_saved = metrics["total_tokens_saved"]
            
            efficiency_score = min(100, (avg_compression * 50) + (total_tokens_saved / 1000))
        else:
            efficiency_score = 0
        
        return {
            "success": True,
            "summary": {
                "total_optimizations": total_optimizations,
                "efficiency_score": efficiency_score,
                "avg_compression_ratio": metrics["avg_compression_ratio"],
                "avg_processing_time_ms": metrics["avg_processing_time_ms"],
                "total_tokens_saved": metrics["total_tokens_saved"],
                "strategy_distribution": metrics["strategy_distribution"],
                "agent_type_distribution": metrics["agent_type_distribution"],
                "recent_optimizations": recent,
            }
        }
    except Exception as exc:
        logger.error("failed to get context optimization summary", extra={"error": str(exc)})
        raise HTTPException(status_code=500, detail="Failed to retrieve summary")


@router.post("/context-optimization/preview", response_model=ContextPreviewResponse)
async def preview_context_optimization(request: ContextPreviewRequest) -> ContextPreviewResponse:
    """Preview context optimization by comparing original vs optimized context."""
    try:
        # Convert request messages to ChatMessage objects
        messages = []
        for msg_data in request.messages:
            messages.append(ChatMessage(
                role=msg_data.get("role", "user"),
                content=msg_data.get("content", ""),
                timestamp=msg_data.get("timestamp", "")
            ))
        
        # Get context optimizer
        optimizer = get_context_optimizer()
        
        # Generate original context (full context)
        original_result = optimizer._optimize_full_context(
            messages=messages,
            current_query=request.current_query,
            max_tokens=request.max_tokens
        )
        
        # Generate optimized context
        optimized_result = optimizer.optimize_context(
            messages=messages,
            current_query=request.current_query,
            agent_type=request.agent_type,
            max_tokens=request.max_tokens
        )
        
        # Build context previews
        original_context = {
            "strategy": original_result.optimization_strategy,
            "message_count": original_result.original_message_count,
            "estimated_tokens": original_result.total_tokens_estimate,
            "segments": [
                {
                    "type": segment.segment_type,
                    "message_count": len(segment.messages),
                    "relevance_score": segment.relevance_score,
                    "relevance_level": segment.relevance_level.value,
                    "content_preview": segment.messages[0].content[:100] + "..." if segment.messages else ""
                }
                for segment in original_result.selected_segments
            ],
            "messages": [
                {
                    "role": msg.role,
                    "content": msg.content[:200] + "..." if len(msg.content) > 200 else msg.content,
                    "timestamp": msg.timestamp
                }
                for msg in messages
            ]
        }
        
        optimized_context = {
            "strategy": optimized_result.optimization_strategy,
            "message_count": optimized_result.optimized_message_count,
            "estimated_tokens": optimized_result.total_tokens_estimate,
            "compression_ratio": optimized_result.compression_ratio,
            "segments": [
                {
                    "type": segment.segment_type,
                    "message_count": len(segment.messages),
                    "relevance_score": segment.relevance_score,
                    "relevance_level": segment.relevance_level.value,
                    "content_preview": segment.messages[0].content[:100] + "..." if segment.messages else ""
                }
                for segment in optimized_result.selected_segments
            ],
            "selected_messages": [
                {
                    "role": msg.role,
                    "content": msg.content[:200] + "..." if len(msg.content) > 200 else msg.content,
                    "timestamp": msg.timestamp
                }
                for segment in optimized_result.selected_segments
                for msg in segment.messages
            ]
        }
        
        # Calculate comparison metrics
        comparison = {
            "message_reduction": original_result.original_message_count - optimized_result.optimized_message_count,
            "message_reduction_percent": (
                (original_result.original_message_count - optimized_result.optimized_message_count) / 
                original_result.original_message_count * 100
            ) if original_result.original_message_count > 0 else 0,
            "token_reduction": original_result.total_tokens_estimate - optimized_result.total_tokens_estimate,
            "token_reduction_percent": (
                (original_result.total_tokens_estimate - optimized_result.total_tokens_estimate) / 
                original_result.total_tokens_estimate * 100
            ) if original_result.total_tokens_estimate > 0 else 0,
            "compression_ratio": optimized_result.compression_ratio,
            "strategy_changed": original_result.optimization_strategy != optimized_result.optimization_strategy,
            "segments_reduced": len(original_result.selected_segments) - len(optimized_result.selected_segments)
        }
        
        logger.info(
            "context optimization preview generated",
            extra={
                "agent_type": request.agent_type,
                "original_messages": original_result.original_message_count,
                "optimized_messages": optimized_result.optimized_message_count,
                "strategy": optimized_result.optimization_strategy,
                "compression_ratio": optimized_result.compression_ratio,
            }
        )
        
        return ContextPreviewResponse(
            success=True,
            original_context=original_context,
            optimized_context=optimized_context,
            comparison=comparison
        )
        
    except Exception as exc:
        logger.error("failed to generate context optimization preview", extra={"error": str(exc)})
        raise HTTPException(status_code=500, detail="Failed to generate preview")


@router.get("/context-optimization/preview/sample")
async def get_sample_context_preview() -> Dict[str, Any]:
    """Get a sample context optimization preview with example data."""
    try:
        # Create sample messages
        sample_messages = [
            {"role": "user", "content": "Hello, how are you?", "timestamp": "2024-01-01 10:00:00"},
            {"role": "assistant", "content": "I'm doing well, thank you!", "timestamp": "2024-01-01 10:01:00"},
            {"role": "user", "content": "Can you help me with email?", "timestamp": "2024-01-01 10:02:00"},
            {"role": "assistant", "content": "Of course! What do you need help with?", "timestamp": "2024-01-01 10:03:00"},
            {"role": "user", "content": "I need to search for emails from John", "timestamp": "2024-01-01 10:04:00"},
            {"role": "assistant", "content": "I'll help you search for emails from John.", "timestamp": "2024-01-01 10:05:00"},
            {"role": "agent", "content": "Tool/Action: Searching Gmail for emails from John...", "timestamp": "2024-01-01 10:06:00"},
            {"role": "agent", "content": "Found 5 emails from John", "timestamp": "2024-01-01 10:07:00"},
            {"role": "assistant", "content": "I found 5 emails from John. Would you like me to show them?", "timestamp": "2024-01-01 10:08:00"},
            {"role": "user", "content": "Yes, please show me the most recent one", "timestamp": "2024-01-01 10:09:00"},
        ]
        
        # Create sample request
        sample_request = ContextPreviewRequest(
            messages=sample_messages,
            current_query="Show me the most recent email from John",
            agent_type="interaction"
        )
        
        # Generate preview
        preview_response = await preview_context_optimization(sample_request)
        
        return {
            "success": True,
            "sample_request": sample_request.dict(),
            "preview": preview_response.dict()
        }
        
    except Exception as exc:
        logger.error("failed to generate sample context preview", extra={"error": str(exc)})
        raise HTTPException(status_code=500, detail="Failed to generate sample preview")
