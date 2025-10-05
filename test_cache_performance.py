#!/usr/bin/env python3
"""
Cache Performance Testing Script for OpenPoke
=============================================

This script tests the conversation caching system performance by:
1. Testing with cache enabled (default)
2. Testing with cache disabled
3. Measuring response times and performance metrics
4. Generating performance comparison reports

Usage:
    python test_cache_performance.py [--disable-cache] [--iterations N] [--concurrent N]
"""

import asyncio
import aiohttp
import time
import json
import argparse
import statistics
from typing import List, Dict, Any
from dataclasses import dataclass
import sys
import os

# Add the server directory to the path for imports
sys.path.append(os.path.join(os.path.dirname(__file__), 'server'))

@dataclass
class PerformanceMetrics:
    """Container for performance test results."""
    test_name: str
    total_requests: int
    successful_requests: int
    failed_requests: int
    avg_response_time: float
    min_response_time: float
    max_response_time: float
    median_response_time: float
    p95_response_time: float
    p99_response_time: float
    requests_per_second: float
    cache_hit_rate: float
    memory_usage_mb: float
    errors: List[str]

class CachePerformanceTester:
    """Test cache performance with various scenarios."""
    
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
    
    async def send_chat_message(self, message: str) -> Dict[str, Any]:
        """Send a chat message and measure response time."""
        start_time = time.time()
        try:
            payload = {
                "messages": [
                    {
                        "role": "user",
                        "content": message
                    }
                ]
            }
            async with self.session.post(
                f"{self.base_url}/api/v1/chat/send", 
                json=payload,
                timeout=aiohttp.ClientTimeout(total=30)
            ) as response:
                end_time = time.time()
                response_time = (end_time - start_time) * 1000  # Convert to milliseconds
                
                if response.status == 200:
                    data = await response.json()
                    return {
                        "success": True,
                        "response_time_ms": response_time,
                        "response": data
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
    
    async def test_conversation_history(self, iterations: int = 10) -> PerformanceMetrics:
        """Test conversation history loading performance."""
        print(f"Testing conversation history loading ({iterations} iterations)...")
        
        response_times = []
        successful_requests = 0
        failed_requests = 0
        errors = []
        
        # Test messages that would trigger conversation history loading
        test_messages = [
            "What did we discuss earlier?",
            "Can you summarize our conversation?",
            "Show me the previous messages",
            "What was the last thing you said?",
            "Tell me about our chat history"
        ]
        
        for i in range(iterations):
            message = test_messages[i % len(test_messages)]
            result = await self.send_chat_message(message)
            
            if result["success"]:
                successful_requests += 1
                response_times.append(result["response_time_ms"])
            else:
                failed_requests += 1
                errors.append(result["error"])
            
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
            median_time = statistics.median(response_times)
            p95_time = self._percentile(response_times, 95)
            p99_time = self._percentile(response_times, 99)
            rps = successful_requests / (sum(response_times) / 1000) if response_times else 0
        else:
            avg_time = min_time = max_time = median_time = p95_time = p99_time = rps = 0
        
        return PerformanceMetrics(
            test_name="Conversation History Loading",
            total_requests=iterations,
            successful_requests=successful_requests,
            failed_requests=failed_requests,
            avg_response_time=avg_time,
            min_response_time=min_time,
            max_response_time=max_time,
            median_response_time=median_time,
            p95_response_time=p95_time,
            p99_response_time=p99_time,
            requests_per_second=rps,
            cache_hit_rate=cache_hit_rate,
            memory_usage_mb=memory_usage,
            errors=errors
        )
    
    async def test_concurrent_requests(self, concurrent_users: int = 5, requests_per_user: int = 3) -> PerformanceMetrics:
        """Test concurrent request handling."""
        print(f"Testing concurrent requests ({concurrent_users} users, {requests_per_user} requests each)...")
        
        async def user_simulation(user_id: int):
            """Simulate a single user making requests."""
            user_response_times = []
            user_successful = 0
            user_failed = 0
            user_errors = []
            
            for i in range(requests_per_user):
                message = f"User {user_id} request {i+1}: What's the weather like?"
                result = await self.send_chat_message(message)
                
                if result["success"]:
                    user_successful += 1
                    user_response_times.append(result["response_time_ms"])
                else:
                    user_failed += 1
                    user_errors.append(result["error"])
                
                # Random delay between requests
                await asyncio.sleep(0.1 + (i * 0.05))
            
            return {
                "response_times": user_response_times,
                "successful": user_successful,
                "failed": user_failed,
                "errors": user_errors
            }
        
        # Run concurrent user simulations
        tasks = [user_simulation(i) for i in range(concurrent_users)]
        results = await asyncio.gather(*tasks)
        
        # Aggregate results
        all_response_times = []
        total_successful = 0
        total_failed = 0
        all_errors = []
        
        for result in results:
            all_response_times.extend(result["response_times"])
            total_successful += result["successful"]
            total_failed += result["failed"]
            all_errors.extend(result["errors"])
        
        # Get cache stats
        cache_stats = await self.get_cache_stats()
        cache_hit_rate = cache_stats.get("cache_hit_rate", 0.0)
        memory_usage = cache_stats.get("memory_usage_mb", 0.0)
        
        # Calculate statistics
        if all_response_times:
            avg_time = statistics.mean(all_response_times)
            min_time = min(all_response_times)
            max_time = max(all_response_times)
            median_time = statistics.median(all_response_times)
            p95_time = self._percentile(all_response_times, 95)
            p99_time = self._percentile(all_response_times, 99)
            rps = total_successful / (sum(all_response_times) / 1000) if all_response_times else 0
        else:
            avg_time = min_time = max_time = median_time = p95_time = p99_time = rps = 0
        
        return PerformanceMetrics(
            test_name="Concurrent Request Handling",
            total_requests=concurrent_users * requests_per_user,
            successful_requests=total_successful,
            failed_requests=total_failed,
            avg_response_time=avg_time,
            min_response_time=min_time,
            max_response_time=max_time,
            median_response_time=median_time,
            p95_response_time=p95_time,
            p99_response_time=p99_time,
            requests_per_second=rps,
            cache_hit_rate=cache_hit_rate,
            memory_usage_mb=memory_usage,
            errors=all_errors
        )
    
    def _percentile(self, data: List[float], percentile: int) -> float:
        """Calculate the nth percentile of a dataset."""
        if not data:
            return 0.0
        sorted_data = sorted(data)
        index = (percentile / 100) * (len(sorted_data) - 1)
        if index.is_integer():
            return sorted_data[int(index)]
        else:
            lower = sorted_data[int(index)]
            upper = sorted_data[int(index) + 1]
            return lower + (upper - lower) * (index - int(index))
    
    def print_metrics(self, metrics: PerformanceMetrics):
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
        print(f"  Median:           {metrics.median_response_time:.2f}")
        print(f"  Min:              {metrics.min_response_time:.2f}")
        print(f"  Max:              {metrics.max_response_time:.2f}")
        print(f"  95th Percentile:  {metrics.p95_response_time:.2f}")
        print(f"  99th Percentile:  {metrics.p99_response_time:.2f}")
        print(f"\nPerformance:")
        print(f"  Requests/sec:     {metrics.requests_per_second:.2f}")
        print(f"  Cache Hit Rate:   {metrics.cache_hit_rate:.1f}%")
        print(f"  Memory Usage:     {metrics.memory_usage_mb:.1f} MB")
        
        if metrics.errors:
            print(f"\nErrors ({len(metrics.errors)}):")
            for error in metrics.errors[:5]:  # Show first 5 errors
                print(f"  - {error}")
            if len(metrics.errors) > 5:
                print(f"  ... and {len(metrics.errors) - 5} more errors")

async def main():
    """Main testing function."""
    parser = argparse.ArgumentParser(description="Test OpenPoke cache performance")
    parser.add_argument("--disable-cache", action="store_true", 
                       help="Test with cache disabled (requires server restart)")
    parser.add_argument("--iterations", type=int, default=10,
                       help="Number of iterations for conversation history test")
    parser.add_argument("--concurrent", type=int, default=5,
                       help="Number of concurrent users for load test")
    parser.add_argument("--base-url", default="http://localhost:8001",
                       help="Base URL of the OpenPoke server")
    
    args = parser.parse_args()
    
    print("OpenPoke Cache Performance Testing")
    print("=" * 50)
    print(f"Server URL: {args.base_url}")
    print(f"Cache Status: {'DISABLED' if args.disable_cache else 'ENABLED'}")
    print(f"Iterations: {args.iterations}")
    print(f"Concurrent Users: {args.concurrent}")
    print()
    
    if args.disable_cache:
        print("⚠️  WARNING: Cache disabled testing requires:")
        print("   1. Stop the server")
        print("   2. Set CONVERSATION_CACHE_MB=0 in .env")
        print("   3. Restart the server")
        print("   4. Run this test")
        print("   5. Re-enable cache and restart for comparison")
        print()
    
    async with CachePerformanceTester(args.base_url) as tester:
        # Get initial cache stats
        print("Getting initial cache statistics...")
        initial_stats = await tester.get_cache_stats()
        print(f"Initial Cache Stats: {json.dumps(initial_stats, indent=2)}")
        print()
        
        # Clear cache before testing
        print("Clearing cache before testing...")
        await tester.clear_cache()
        
        # Test 1: Conversation History Loading
        history_metrics = await tester.test_conversation_history(args.iterations)
        tester.print_metrics(history_metrics)
        
        # Test 2: Concurrent Requests
        concurrent_metrics = await tester.test_concurrent_requests(args.concurrent, 3)
        tester.print_metrics(concurrent_metrics)
        
        # Get final cache stats
        print("\nGetting final cache statistics...")
        final_stats = await tester.get_cache_stats()
        print(f"Final Cache Stats: {json.dumps(final_stats, indent=2)}")
        
        # Summary
        print(f"\n{'='*60}")
        print("PERFORMANCE SUMMARY")
        print(f"{'='*60}")
        print(f"Conversation History Test:")
        print(f"  Avg Response Time: {history_metrics.avg_response_time:.2f}ms")
        print(f"  Cache Hit Rate:    {history_metrics.cache_hit_rate:.1f}%")
        print(f"  Memory Usage:      {history_metrics.memory_usage_mb:.1f}MB")
        print(f"\nConcurrent Load Test:")
        print(f"  Avg Response Time: {concurrent_metrics.avg_response_time:.2f}ms")
        print(f"  Requests/sec:      {concurrent_metrics.requests_per_second:.2f}")
        print(f"  Cache Hit Rate:    {concurrent_metrics.cache_hit_rate:.1f}%")

if __name__ == "__main__":
    asyncio.run(main())
