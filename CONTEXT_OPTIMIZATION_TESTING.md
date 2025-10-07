# Context Optimization Testing Guide

## Overview

This guide explains how to run and understand the Context Optimization tests in OpenPoke. The tests verify that the context optimization feature works correctly by reducing token usage while maintaining conversation quality.

## Test Objectives

The Context Optimization tests verify:

1. **Smart Context Selection** - Only relevant conversation history is sent to the LLM
2. **Token Reduction** - Context size is optimized to reduce API costs
3. **Quality Preservation** - Important conversation context is maintained
4. **Performance** - Optimization happens quickly without delays
5. **Agent Integration** - Both interaction and execution agents use optimization seamlessly

## Running Tests

### Quick Start

```bash
# Run all context optimization tests
python3 run_context_optimization_tests.py

# Run specific test file
python3 run_context_optimization_tests.py test:test_context_optimizer.py

# Generate coverage report
python3 run_context_optimization_tests.py coverage
```

### Using pytest directly

```bash
# Activate virtual environment
source openpoke-env/bin/activate

# Run all tests
pytest tests/test_context_optimizer.py tests/test_context_metrics.py tests/test_agent_integration.py tests/test_context_optimization_integration.py tests/test_context_optimization_api.py -v

# Run specific test file
pytest tests/test_context_optimizer.py -v
```

## Test Files

| Test File | Purpose |
|-----------|---------|
| `test_context_optimizer.py` | Core optimization logic and strategies |
| `test_context_metrics.py` | Performance monitoring and statistics |
| `test_agent_integration.py` | Agent integration with optimization |
| `test_context_optimization_integration.py` | End-to-end system testing |
| `test_context_optimization_api.py` | API endpoint testing |

## Understanding Test Output

### Successful Test Run

```
✅ tests/test_context_optimizer.py passed
✅ tests/test_context_metrics.py passed
✅ tests/test_agent_integration.py passed
✅ tests/test_context_optimization_integration.py passed
✅ tests/test_context_optimization_api.py passed

📊 Test Results:
   Total Tests: 45
   Passed: 45
   Failed: 0
🎉 All tests passed!
```

### Failed Test Run

```
❌ tests/test_context_optimizer.py failed
STDOUT: ============================= test session starts ==============================
FAILED tests/test_context_optimizer.py::TestContextOptimizer::test_optimize_context_small_conversation - AssertionError: Expected compression ratio > 0.5

📊 Test Results:
   Total Tests: 45
   Passed: 40
   Failed: 5
💥 Some tests failed!
```

## Key Test Metrics

### 1. **Compression Ratio**
- **What it measures**: How much the context was reduced
- **Good value**: 0.3-0.7 (30-70% reduction)
- **Example**: 0.5 means context was reduced by 50%

### 2. **Token Savings**
- **What it measures**: Estimated tokens saved per optimization
- **Good value**: 100-1000+ tokens depending on conversation size
- **Example**: 500 tokens saved = ~$0.0015 cost reduction

### 3. **Processing Time**
- **What it measures**: Time taken to optimize context
- **Good value**: < 100ms for most conversations
- **Example**: 50ms = very fast optimization

### 4. **Relevance Score**
- **What it measures**: How relevant selected context is to current query
- **Good value**: 0.6-1.0 (60-100% relevant)
- **Example**: 0.8 means 80% of selected context is relevant

### 5. **Strategy Distribution**
- **What it measures**: Which optimization strategies are used
- **Good distribution**: Mix of smart_selection, recent_only, full_context
- **Example**: 60% smart_selection, 30% recent_only, 10% full_context

## Test Evaluation Criteria

### Performance Benchmarks

| Conversation Size | Expected Processing Time | Expected Compression |
|-------------------|-------------------------|---------------------|
| Small (5-10 messages) | < 10ms | 0.1-0.3 |
| Medium (20-50 messages) | < 50ms | 0.3-0.6 |
| Large (100+ messages) | < 100ms | 0.5-0.8 |

### Quality Metrics

| Metric | Minimum | Target | Excellent |
|--------|---------|--------|-----------|
| Compression Ratio | 0.2 | 0.4 | 0.6+ |
| Relevance Score | 0.5 | 0.7 | 0.8+ |
| Processing Time | < 200ms | < 100ms | < 50ms |
| Token Savings | 50+ | 200+ | 500+ |

## Context Preview API

Test the context optimization by comparing original vs optimized context:

```bash
# Preview context optimization
curl -X POST "http://localhost:8000/api/v1/context-optimization/preview" \
  -H "Content-Type: application/json" \
  -d '{
    "messages": [
      {"role": "user", "content": "Hello", "timestamp": "2024-01-01 10:00:00"},
      {"role": "assistant", "content": "Hi there!", "timestamp": "2024-01-01 10:01:00"},
      {"role": "user", "content": "Help me search emails", "timestamp": "2024-01-01 10:02:00"}
    ],
    "current_query": "Search for emails from John",
    "agent_type": "interaction"
  }'
```

### Sample Response

```json
{
  "original_context": {
    "message_count": 3,
    "estimated_tokens": 150,
    "content": "Hello\nHi there!\nHelp me search emails"
  },
  "optimized_context": {
    "message_count": 2,
    "estimated_tokens": 100,
    "content": "Help me search emails\nSearch for emails from John",
    "strategy": "smart_selection",
    "compression_ratio": 0.33
  },
  "metrics": {
    "tokens_saved": 50,
    "compression_ratio": 0.33,
    "relevance_score": 0.85
  }
}
```

## Troubleshooting

### Common Issues

1. **Import Errors**: Ensure virtual environment is activated
2. **Test Failures**: Check if context optimization is enabled in config
3. **Slow Tests**: Large conversations may take longer to process
4. **API Errors**: Ensure server is running for API tests

### Getting Help

1. Check test output for specific error messages
2. Run individual test files to isolate issues
3. Verify all dependencies are installed
4. Check server configuration and environment variables

## Success Criteria

Tests pass when:

- ✅ All optimization strategies work correctly
- ✅ Context is reduced by 20-80% without losing important information
- ✅ Processing time is under 100ms for most conversations
- ✅ Agent integration works seamlessly
- ✅ API endpoints return correct data
- ✅ Error handling works gracefully

The tests ensure Context Optimization provides significant token savings while maintaining conversation quality and system performance.