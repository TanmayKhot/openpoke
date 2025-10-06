# How to Use the Caching System Tests

## 1. How to Run the Tests

### Prerequisites


# Install pytest if not already installed
pip install pytest

### Running Tests
```bash
# Run all tests
python -m pytest test_caching_system.py -v

# Run specific test categories
python -m pytest test_caching_system.py::TestConversationCache -v
python -m pytest test_caching_system.py::TestResponseCache -v
python -m pytest test_caching_system.py::TestHybridCacheStrategy -v
python -m pytest test_caching_system.py::TestCacheIntegration -v
python -m pytest test_caching_system.py::TestCacheEndpoints -v
python -m pytest test_caching_system.py::TestProductionScenarios -v

# Run with coverage
python -m pytest test_caching_system.py --cov=server.services.conversation --cov=server.openrouter_client
```

## 2. What is the Purpose of the Test

The test suite validates the OpenPoke caching system functionality across multiple components:

- **TestConversationCache**: Tests conversation cache initialization, storage, retrieval, LRU eviction, memory eviction, and statistics
- **TestResponseCache**: Tests response cache key generation, storage/retrieval, statistics, and clearing
- **TestHybridCacheStrategy**: Tests intelligent caching policies based on tools, intent, content patterns, and static content
- **TestCacheIntegration**: Tests end-to-end integration between cache systems
- **TestCacheEndpoints**: Tests API endpoints for cache management

## 3. How to Interpret the Results

### Metrics Measured to Ensure Correct Test Execution

**Cache Performance Metrics:**
- Cache hit/miss ratios
- Memory usage and eviction behavior
- Response time for cache operations
- Cache size limits and LRU eviction accuracy

**Functional Correctness Metrics:**
- Data integrity (stored data matches retrieved data)
- Cache key generation uniqueness
- Cache invalidation timing
- Statistics accuracy (hit counts, miss counts, size)

**Integration Metrics:**
- End-to-end cache behavior consistency
- Cross-component data flow accuracy
- API endpoint response correctness
- Real-world scenario simulation accuracy

**Key Result Indicators:**
- **PASSED**: All metrics within expected ranges, functionality works as expected
- **FAILED**: One or more metrics outside expected ranges, indicates incorrect behavior
- **ERROR**: System or configuration issue preventing metric collection
- **SKIPPED**: Test skipped due to missing dependencies or conditions
