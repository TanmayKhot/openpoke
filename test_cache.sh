#!/bin/bash
# OpenPoke Cache Testing Script
# ===========================
# This script provides easy commands to test the cache system

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
SERVER_URL="http://localhost:8001"
WEB_URL="http://localhost:3000"
ITERATIONS=10
CONCURRENT_USERS=5

# Functions
print_header() {
    echo -e "${BLUE}================================${NC}"
    echo -e "${BLUE}$1${NC}"
    echo -e "${BLUE}================================${NC}"
}

print_success() {
    echo -e "${GREEN}✅ $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

print_error() {
    echo -e "${RED}❌ $1${NC}"
}

check_server() {
    print_header "Checking Server Status"
    
    if curl -s -f "$SERVER_URL/api/v1/cache/stats" > /dev/null 2>&1; then
        print_success "Server is running at $SERVER_URL"
        return 0
    else
        print_error "Server is not running or not accessible at $SERVER_URL"
        echo "Please start the server with: source openpoke-env/bin/activate && python -m server.server"
        return 1
    fi
}

get_cache_stats() {
    print_header "Current Cache Statistics"
    curl -s "$SERVER_URL/api/v1/cache/stats" | python3 -m json.tool
}

clear_cache() {
    print_header "Clearing Cache"
    if curl -s -X POST "$SERVER_URL/api/v1/cache/clear" > /dev/null; then
        print_success "Cache cleared successfully"
    else
        print_error "Failed to clear cache"
    fi
}

preload_cache() {
    print_header "Preloading Cache"
    if curl -s -X POST "$SERVER_URL/api/v1/cache/preload" > /dev/null; then
        print_success "Cache preloaded successfully"
    else
        print_error "Failed to preload cache"
    fi
}

test_chat_performance() {
    print_header "Testing Chat Performance"
    
    echo "Sending test messages..."
    
    # Test message 1
    echo -n "Test 1 - Simple message: "
    start_time=$(date +%s.%N)
    response=$(curl -s -X POST "$SERVER_URL/api/v1/chat" \
        -H "Content-Type: application/json" \
        -d '{"message": "Hello, how are you?"}')
    end_time=$(date +%s.%N)
    duration=$(echo "$end_time - $start_time" | bc)
    echo "${duration}s"
    
    # Test message 2 (should hit cache)
    echo -n "Test 2 - Cache hit test: "
    start_time=$(date +%s.%N)
    response=$(curl -s -X POST "$SERVER_URL/api/v1/chat" \
        -H "Content-Type: application/json" \
        -d '{"message": "What did we just discuss?"}')
    end_time=$(date +%s.%N)
    duration=$(echo "$end_time - $start_time" | bc)
    echo "${duration}s"
    
    # Test message 3 (conversation history)
    echo -n "Test 3 - History request: "
    start_time=$(date +%s.%N)
    response=$(curl -s -X POST "$SERVER_URL/api/v1/chat" \
        -H "Content-Type: application/json" \
        -d '{"message": "Can you summarize our conversation?"}')
    end_time=$(date +%s.%N)
    duration=$(echo "$end_time - $start_time" | bc)
    echo "${duration}s"
}

run_performance_test() {
    print_header "Running Comprehensive Performance Test"
    
    if [ -f "test_cache_performance.py" ]; then
        echo "Running Python performance test script..."
        python3 test_cache_performance.py --iterations $ITERATIONS --concurrent $CONCURRENT_USERS
    else
        print_error "test_cache_performance.py not found"
        echo "Please ensure the performance test script is in the current directory"
    fi
}

test_without_cache() {
    print_header "Testing Without Cache"
    
    print_warning "To test without cache, you need to:"
    echo "1. Stop the server (Ctrl+C)"
    echo "2. Set CONVERSATION_CACHE_MB=0 in .env file"
    echo "3. Restart the server"
    echo "4. Run this script again"
    echo ""
    echo "To re-enable cache:"
    echo "1. Stop the server"
    echo "2. Set CONVERSATION_CACHE_MB=512 in .env file"
    echo "3. Restart the server"
}

compare_performance() {
    print_header "Performance Comparison"
    
    echo "This will run tests with cache enabled and disabled for comparison."
    echo ""
    echo "Step 1: Testing with cache ENABLED"
    echo "-----------------------------------"
    get_cache_stats
    test_chat_performance
    
    echo ""
    echo "Step 2: Testing with cache DISABLED"
    echo "-----------------------------------"
    test_without_cache
}

show_help() {
    echo "OpenPoke Cache Testing Script"
    echo "============================="
    echo ""
    echo "Usage: $0 [COMMAND]"
    echo ""
    echo "Commands:"
    echo "  status      - Check server status and cache statistics"
    echo "  stats       - Show current cache statistics"
    echo "  clear       - Clear the conversation cache"
    echo "  preload     - Preload the conversation cache"
    echo "  test        - Run basic chat performance tests"
    echo "  performance - Run comprehensive performance tests"
    echo "  compare     - Compare performance with/without cache"
    echo "  help        - Show this help message"
    echo ""
    echo "Examples:"
    echo "  $0 status"
    echo "  $0 test"
    echo "  $0 performance"
    echo ""
    echo "Configuration:"
    echo "  Server URL: $SERVER_URL"
    echo "  Web URL: $WEB_URL"
    echo "  Test Iterations: $ITERATIONS"
    echo "  Concurrent Users: $CONCURRENT_USERS"
}

# Main script logic
case "${1:-help}" in
    "status")
        check_server && get_cache_stats
        ;;
    "stats")
        check_server && get_cache_stats
        ;;
    "clear")
        check_server && clear_cache
        ;;
    "preload")
        check_server && preload_cache
        ;;
    "test")
        check_server && test_chat_performance
        ;;
    "performance")
        check_server && run_performance_test
        ;;
    "compare")
        check_server && compare_performance
        ;;
    "help"|"--help"|"-h")
        show_help
        ;;
    *)
        print_error "Unknown command: $1"
        echo ""
        show_help
        exit 1
        ;;
esac
