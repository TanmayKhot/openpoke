"""Hybrid caching approach used in production systems."""

from __future__ import annotations

import json
import threading
import time
from typing import Any, Dict, List, Optional, Tuple
from dataclasses import dataclass
from enum import Enum

from ...logging_config import logger


class CacheDecision(Enum):
    """Cache decision types."""
    CACHE_PERMANENT = "cache_permanent"     # Cache forever
    CACHE_WITH_TTL = "cache_with_ttl"     # Cache with TTL
    DONT_CACHE = "dont_cache"             # Don't cache
    CACHE_CONDITIONAL = "cache_conditional" # Cache based on conditions


@dataclass
class CachePolicy:
    """Cache policy for a request."""
    
    decision: CacheDecision
    ttl_seconds: Optional[int] = None
    confidence: float = 0.0
    reasoning: str = ""
    conditions: List[str] = None
    
    def __post_init__(self):
        if self.conditions is None:
            self.conditions = []


class HybridCacheStrategy:
    """
    Hybrid caching strategy combining multiple approaches.
    
    This is similar to what production systems use:
    - Google Search: Uses query analysis + result analysis
    - Facebook Feed: Uses user context + content analysis  
    - Twitter Timeline: Uses user behavior + content freshness
    """
    
    def __init__(self):
        """Initialize hybrid cache strategy."""
        
        # Approach 1: Tool-based analysis (most reliable)
        self.tool_policies = {
            # Data retrieval tools
            "gmail_search": CachePolicy(CacheDecision.CACHE_WITH_TTL, 300, 0.95, "Email data changes frequently"),
            "weather_api": CachePolicy(CacheDecision.CACHE_WITH_TTL, 900, 0.9, "Weather updates every 15 minutes"),
            "stock_price": CachePolicy(CacheDecision.CACHE_WITH_TTL, 60, 0.95, "Stock prices change constantly"),
            "bank_balance": CachePolicy(CacheDecision.CACHE_WITH_TTL, 300, 0.95, "Bank data is sensitive and changes"),
            
            # Analysis tools (usually static)
            "text_analysis": CachePolicy(CacheDecision.CACHE_PERMANENT, None, 0.9, "Text analysis results are deterministic"),
            "sentiment_analysis": CachePolicy(CacheDecision.CACHE_PERMANENT, None, 0.9, "Sentiment analysis is deterministic"),
            "language_translation": CachePolicy(CacheDecision.CACHE_PERMANENT, None, 0.95, "Translation is deterministic"),
            
            # Action tools (never cache)
            "send_email": CachePolicy(CacheDecision.DONT_CACHE, None, 1.0, "Actions should not be cached"),
            "create_calendar_event": CachePolicy(CacheDecision.DONT_CACHE, None, 1.0, "Actions should not be cached"),
        }
        
        # Approach 2: Intent-based analysis
        self.intent_policies = {
            "check_status": CachePolicy(CacheDecision.CACHE_WITH_TTL, 300, 0.8, "Status checks are time-sensitive"),
            "get_balance": CachePolicy(CacheDecision.CACHE_WITH_TTL, 300, 0.8, "Balance queries are time-sensitive"),
            "check_weather": CachePolicy(CacheDecision.CACHE_WITH_TTL, 900, 0.7, "Weather queries have medium TTL"),
            "explain_concept": CachePolicy(CacheDecision.CACHE_PERMANENT, None, 0.9, "Explanations are static"),
            "solve_problem": CachePolicy(CacheDecision.CACHE_PERMANENT, None, 0.9, "Problem solutions are deterministic"),
        }
        
        # Approach 3: Content-based analysis (fallback)
        self.content_patterns = {
            # High confidence dynamic patterns
            r"\b(your|you have)\s+\d+\s+(emails?|messages?|notifications?)\b": 
                CachePolicy(CacheDecision.DONT_CACHE, None, 0.95, "Personal data changes frequently"),
            
            r"\b(your|you)\s+(balance|account|portfolio)\s+(is|shows)\s+\$?\d+": 
                CachePolicy(CacheDecision.CACHE_WITH_TTL, 300, 0.9, "Financial data is time-sensitive"),
            
            r"\b(current|now|today|this (?:morning|afternoon|evening))\b": 
                CachePolicy(CacheDecision.CACHE_WITH_TTL, 300, 0.8, "Time-sensitive content"),
            
            # High confidence static patterns
            r"\b(what is|explain|define)\s+": 
                CachePolicy(CacheDecision.CACHE_PERMANENT, None, 0.9, "Definition queries are static"),
            
            r"\b(calculate|solve|compute)\s+": 
                CachePolicy(CacheDecision.CACHE_PERMANENT, None, 0.9, "Calculations are deterministic"),
        }
        
        # Approach 4: User behavior analysis (learning)
        self.user_behavior_cache = {}  # In production, this would be persistent
        
        logger.info(
            "hybrid cache strategy initialized",
            extra={
                "tool_policies": len(self.tool_policies),
                "intent_policies": len(self.intent_policies),
                "content_patterns": len(self.content_patterns),
            }
        )
    
    def determine_cache_policy(
        self, 
        request_data: Dict[str, Any], 
        response_data: Optional[Dict[str, Any]] = None,
        user_id: Optional[str] = None
    ) -> CachePolicy:
        """
        Determine cache policy using hybrid approach.
        
        Args:
            request_data: Request data
            response_data: Response data (optional)
            user_id: User ID for behavior analysis
            
        Returns:
            Cache policy to apply
        """
        policies = []
        
        # Approach 1: Tool-based analysis (highest priority)
        tool_policy = self._analyze_tools(request_data)
        if tool_policy:
            policies.append(tool_policy)
        
        # Approach 2: Intent-based analysis
        intent_policy = self._analyze_intent(request_data)
        if intent_policy:
            policies.append(intent_policy)
        
        # Approach 3: Content-based analysis
        content_policy = self._analyze_content(request_data, response_data)
        if content_policy:
            policies.append(content_policy)
        
        # Approach 4: User behavior analysis
        behavior_policy = self._analyze_user_behavior(request_data, user_id)
        if behavior_policy:
            policies.append(behavior_policy)
        
        # Combine policies (use highest confidence)
        if policies:
            # Sort by confidence and use the highest
            best_policy = max(policies, key=lambda p: p.confidence)
            
            logger.debug(
                "cache policy determined",
                extra={
                    "policies_evaluated": len(policies),
                    "best_policy": best_policy.decision.value,
                    "confidence": best_policy.confidence,
                    "reasoning": best_policy.reasoning,
                }
            )
            
            return best_policy
        
        # Default policy for unknown cases
        default_policy = CachePolicy(
            CacheDecision.CACHE_WITH_TTL, 
            1800,  # 30 minutes default
            0.5, 
            "Default policy for unknown request type"
        )
        
        logger.debug("using default cache policy")
        return default_policy
    
    def _analyze_tools(self, request_data: Dict[str, Any]) -> Optional[CachePolicy]:
        """Analyze tools used in request."""
        tools = request_data.get("tools", [])
        if not tools:
            return None
        
        # Check if any tools have specific policies
        for tool in tools:
            if isinstance(tool, dict) and "function" in tool:
                tool_name = tool["function"].get("name", "")
                if tool_name in self.tool_policies:
                    return self.tool_policies[tool_name]
        
        return None
    
    def _analyze_intent(self, request_data: Dict[str, Any]) -> Optional[CachePolicy]:
        """Analyze user intent from messages."""
        messages = request_data.get("messages", [])
        if not messages:
            return None
        
        # Get the last user message
        user_message = None
        for message in reversed(messages):
            if message.get("role") == "user":
                user_message = message.get("content", "").lower()
                break
        
        if not user_message:
            return None
        
        # Check intent patterns
        for intent, policy in self.intent_policies.items():
            intent_patterns = {
                "check_status": ["check", "status", "how is", "what's the status"],
                "get_balance": ["balance", "how much", "amount", "money"],
                "check_weather": ["weather", "temperature", "forecast"],
                "explain_concept": ["explain", "what is", "how does", "tell me about"],
                "solve_problem": ["solve", "calculate", "compute", "figure out"],
            }
            
            if intent in intent_patterns:
                patterns = intent_patterns[intent]
                if any(pattern in user_message for pattern in patterns):
                    return policy
        
        return None
    
    def _analyze_content(
        self, 
        request_data: Dict[str, Any], 
        response_data: Optional[Dict[str, Any]]
    ) -> Optional[CachePolicy]:
        """Analyze content for dynamic patterns."""
        import re
        
        # Analyze request content
        messages = request_data.get("messages", [])
        content_to_analyze = ""
        
        # Get user message
        for message in reversed(messages):
            if message.get("role") == "user":
                content_to_analyze += message.get("content", "").lower()
                break
        
        # Analyze response content if available
        if response_data:
            choices = response_data.get("choices", [])
            if choices and len(choices) > 0:
                message = choices[0].get("message", {})
                content_to_analyze += " " + message.get("content", "").lower()
        
        # Check content patterns
        for pattern, policy in self.content_patterns.items():
            if re.search(pattern, content_to_analyze, re.IGNORECASE):
                return policy
        
        return None
    
    def _analyze_user_behavior(
        self, 
        request_data: Dict[str, Any], 
        user_id: Optional[str]
    ) -> Optional[CachePolicy]:
        """Analyze user behavior patterns."""
        if not user_id:
            return None
        
        # In production, this would analyze:
        # - User's typical request patterns
        # - How often they ask for the same information
        # - Whether they typically need fresh data
        
        # For now, return None (would be implemented with user data)
        return None
    
    def learn_from_decision(
        self, 
        request_data: Dict[str, Any], 
        policy: CachePolicy, 
        was_hit: bool,
        user_feedback: Optional[str] = None
    ) -> None:
        """
        Learn from cache decisions to improve future policies.
        
        Args:
            request_data: Original request data
            policy: Cache policy that was applied
            was_hit: Whether cache hit occurred
            user_feedback: Optional user feedback about freshness
        """
        # In production, this would:
        # - Track cache hit rates for different policy types
        # - Learn from user feedback about stale data
        # - Adjust confidence scores based on outcomes
        # - Update policies based on real-world performance
        
        logger.debug(
            "learning from cache decision",
            extra={
                "policy": policy.decision.value,
                "was_hit": was_hit,
                "user_feedback": user_feedback,
            }
        )


# Global hybrid strategy instance
_hybrid_cache_strategy: Optional[HybridCacheStrategy] = None
_strategy_lock = threading.Lock()


def get_hybrid_cache_strategy() -> HybridCacheStrategy:
    """Get global hybrid cache strategy instance."""
    global _hybrid_cache_strategy
    if _hybrid_cache_strategy is None:
        with _strategy_lock:
            if _hybrid_cache_strategy is None:
                _hybrid_cache_strategy = HybridCacheStrategy()
    return _hybrid_cache_strategy


__all__ = [
    "HybridCacheStrategy",
    "CachePolicy",
    "CacheDecision", 
    "get_hybrid_cache_strategy"
]
