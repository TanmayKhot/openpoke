#!/usr/bin/env python3
"""
Simplified Cache Performance Testing Script for OpenPoke
=======================================================

This script tests the conversation caching system performance by:
1. Testing cache statistics and management endpoints
2. Testing conversation history loading (which uses the cache)
3. Measuring performance improvements

Usage:
    python test_cache_simple.py
"""

import asyncio
import aiohttp
import time
import json
import statistics
from typing import List, Dict, Any
from dataclasses import dataclass

@dataclass
class SimpleMetrics:
    """Container for simple performance test results."""
    test_name: str
    total_requests: int
    successful_requests: int
    failed_requests: int
    avg_response_time: float
    min_response_time: float
    max_response_time: float
    cache_hit_rate: float
    memory_usage_mb: float
    errors: List[str]

class SimpleCacheTester:
    """Simple cache performance tester."""
    
    def __init__(self, base_url: str = "http://localhost:8001"):
        self.base_url = base_url
        self.session = None
        
    async def __aenter__(self):
        self.session = aiohttp.ClientSession()
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()
    
    async def get_cache_stats(self) -> Dict[str, Any]:
        """Get current cache statistics."""
        try:
            async with self.session.get(f"{self.base_url}/api/v1/cache/stats") as response:
                if response.status == 200:
                    return await response.json()
                else:
                    return {"error": f"HTTP {response.status}"}
        except Exception as e:
            return {"error": str(e)}
    
    async def clear_cache(self) -> bool:
        """Clear the conversation cache."""
        try:
            async with self.session.post(f"{self.base_url}/api/v1/cache/clear") as response:
                return response.status == 200
        except Exception:
            return False
    
    async def preload_cache(self) -> bool:
        """Preload the conversation cache."""
        try:
            async with self.session.post(f"{self.base_url}/api/v1/cache/preload") as response:
                return response.status == 200
        except Exception:
            return False
    
    async def get_chat_history(self) -> Dict[str, Any]:
        """Get chat history and measure response time."""
        start_time = time.time()
        try:
            async with self.session.get(
                f"{self.base_url}/api/v1/chat/history",
                timeout=aiohttp.ClientTimeout(total=10)
            ) as response:
                end_time = time.time()
                response_time = (end_time - start_time) * 1000  # Convert to milliseconds
                
                if response.status == 200:
                    data = await response.json()
                    return {
                        "success": True,
                        "response_time_ms": response_time,
                        "response": data,
                        "message_count": len(data.get("messages", []))
                    }
                else:
                    return {
                        "success": False,
                        "response_time_ms": response_time,
                        "error": f"HTTP {response.status}"
                    }
        except Exception as e:
            end_time = time.time()
            response_time = (end_time - start_time) * 1000
            return {
                "success": False,
                "response_time_ms": response_time,
                "error": str(e)
            }
    
    async def test_chat_history_performance(self, iterations: int = 10) -> SimpleMetrics:
        """Test chat history loading performance."""
        print(f"Testing chat history loading ({iterations} iterations)...")
        
        response_times = []
        successful_requests = 0
        failed_requests = 0
        errors = []
        
        for i in range(iterations):
            result = await self.get_chat_history()
            
            if result["success"]:
                successful_requests += 1
                response_times.append(result["response_time_ms"])
                print(f"  Request {i+1}: {result['response_time_ms']:.2f}ms ({result['message_count']} messages)")
            else:
                failed_requests += 1
                errors.append(result["error"])
                print(f"  Request {i+1}: FAILED - {result['error']}")
            
            # Small delay between requests
            await asyncio.sleep(0.1)
        
        # Get cache stats
        cache_stats = await self.get_cache_stats()
        cache_hit_rate = cache_stats.get("cache_hit_rate", 0.0)
        memory_usage = cache_stats.get("memory_usage_mb", 0.0)
        
        # Calculate statistics
        if response_times:
            avg_time = statistics.mean(response_times)
            min_time = min(response_times)
            max_time = max(response_times)
        else:
            avg_time = min_time = max_time = 0
        
        return SimpleMetrics(
            test_name="Chat History Loading",
            total_requests=iterations,
            successful_requests=successful_requests,
            failed_requests=failed_requests,
            avg_response_time=avg_time,
            min_response_time=min_time,
            max_response_time=max_time,
            cache_hit_rate=cache_hit_rate,
            memory_usage_mb=memory_usage,
            errors=errors
        )
    
    def print_metrics(self, metrics: SimpleMetrics):
        """Print formatted performance metrics."""
        print(f"\n{'='*60}")
        print(f"TEST: {metrics.test_name}")
        print(f"{'='*60}")
        print(f"Total Requests:     {metrics.total_requests}")
        print(f"Successful:         {metrics.successful_requests}")
        print(f"Failed:             {metrics.failed_requests}")
        print(f"Success Rate:       {(metrics.successful_requests/metrics.total_requests)*100:.1f}%")
        print(f"\nResponse Times (ms):")
        print(f"  Average:          {metrics.avg_response_time:.2f}")
        print(f"  Min:              {metrics.min_response_time:.2f}")
        print(f"  Max:              {metrics.max_response_time:.2f}")
        print(f"\nCache Performance:")
        print(f"  Cache Hit Rate:   {metrics.cache_hit_rate:.1f}%")
        print(f"  Memory Usage:     {metrics.memory_usage_mb:.1f} MB")
        
        if metrics.errors:
            print(f"\nErrors ({len(metrics.errors)}):")
            for error in metrics.errors[:3]:  # Show first 3 errors
                print(f"  - {error}")
            if len(metrics.errors) > 3:
                print(f"  ... and {len(metrics.errors) - 3} more errors")

async def main():
    """Main testing function."""
    print("OpenPoke Simple Cache Performance Testing")
    print("=" * 50)
    print(f"Server URL: http://localhost:8001")
    print(f"Test Focus: Cache functionality via chat history endpoint")
    print()
    
    async with SimpleCacheTester() as tester:
        # Get initial cache stats
        print("Getting initial cache statistics...")
        initial_stats = await tester.get_cache_stats()
        print(f"Initial Cache Stats: {json.dumps(initial_stats, indent=2)}")
        print()
        
        # Clear cache before testing
        print("Clearing cache before testing...")
        await tester.clear_cache()
        
        # Test 1: Chat History Loading (this will populate the cache)
        print("\n" + "="*60)
        print("TEST 1: First Load (Cache Miss)")
        print("="*60)
        history_metrics_1 = await tester.test_chat_history_performance(5)
        tester.print_metrics(history_metrics_1)
        
        # Test 2: Chat History Loading (this should hit the cache)
        print("\n" + "="*60)
        print("TEST 2: Second Load (Cache Hit)")
        print("="*60)
        history_metrics_2 = await tester.test_chat_history_performance(5)
        tester.print_metrics(history_metrics_2)
        
        # Get final cache stats
        print("\nGetting final cache statistics...")
        final_stats = await tester.get_cache_stats()
        print(f"Final Cache Stats: {json.dumps(final_stats, indent=2)}")
        
        # Summary
        print(f"\n{'='*60}")
        print("PERFORMANCE COMPARISON")
        print(f"{'='*60}")
        print(f"First Load (Cache Miss):")
        print(f"  Avg Response Time: {history_metrics_1.avg_response_time:.2f}ms")
        print(f"  Cache Hit Rate:    {history_metrics_1.cache_hit_rate:.1f}%")
        print(f"  Memory Usage:      {history_metrics_1.memory_usage_mb:.1f}MB")
        print(f"\nSecond Load (Cache Hit):")
        print(f"  Avg Response Time: {history_metrics_2.avg_response_time:.2f}ms")
        print(f"  Cache Hit Rate:    {history_metrics_2.cache_hit_rate:.1f}%")
        print(f"  Memory Usage:      {history_metrics_2.memory_usage_mb:.1f}MB")
        
        if history_metrics_1.avg_response_time > 0 and history_metrics_2.avg_response_time > 0:
            improvement = history_metrics_1.avg_response_time / history_metrics_2.avg_response_time
            print(f"\nPerformance Improvement: {improvement:.1f}x faster with cache")
        
        print(f"\nCache Status:")
        print(f"  Entries: {final_stats.get('entries_count', 0)}")
        print(f"  Memory: {final_stats.get('memory_usage_mb', 0):.1f}MB / {final_stats.get('memory_limit_mb', 0):.1f}MB")
        print(f"  Hit Rate: {final_stats.get('cache_hit_rate', 0):.1f}%")

if __name__ == "__main__":
    asyncio.run(main())