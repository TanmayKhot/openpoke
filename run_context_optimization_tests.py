#!/usr/bin/env python3
"""Test runner for context optimization tests."""

import sys
import subprocess
import os
from pathlib import Path

def run_tests():
    """Run all context optimization tests."""
    # Get the project root directory
    project_root = Path(__file__).parent
    
    # Add the server directory to Python path
    server_dir = project_root / "server"
    if str(server_dir) not in sys.path:
        sys.path.insert(0, str(server_dir))
    
    # Set up environment variables for testing
    os.environ.setdefault("OPENROUTER_API_KEY", "test-key")
    os.environ.setdefault("CONTEXT_OPTIMIZATION_ENABLED", "true")
    
    # Test files to run
    test_files = [
        "tests/test_context_optimizer.py",
        "tests/test_context_metrics.py", 
        "tests/test_agent_integration.py",
        "tests/test_context_optimization_integration.py",
        "tests/test_context_optimization_api.py",
    ]
    
    print("🧪 Running Context Optimization Tests")
    print("=" * 50)
    
    total_tests = 0
    passed_tests = 0
    failed_tests = 0
    
    for test_file in test_files:
        test_path = project_root / test_file
        if not test_path.exists():
            print(f"❌ Test file not found: {test_file}")
            continue
            
        print(f"\n📋 Running {test_file}...")
        
        try:
            # Run pytest on the test file using the virtual environment
            result = subprocess.run([
                "bash", "-c", 
                f"source openpoke-env/bin/activate && python -m pytest {test_path} -v --tb=short --no-header"
            ], capture_output=True, text=True, cwd=project_root)
            
            if result.returncode == 0:
                print(f"✅ {test_file} passed")
                # Count tests from output
                lines = result.stdout.split('\n')
                for line in lines:
                    if 'PASSED' in line:
                        passed_tests += 1
                        total_tests += 1
            else:
                print(f"❌ {test_file} failed")
                print("STDOUT:", result.stdout)
                print("STDERR:", result.stderr)
                failed_tests += 1
                
        except Exception as e:
            print(f"❌ Error running {test_file}: {e}")
            failed_tests += 1
    
    print("\n" + "=" * 50)
    print(f"📊 Test Results:")
    print(f"   Total Tests: {total_tests}")
    print(f"   Passed: {passed_tests}")
    print(f"   Failed: {failed_tests}")
    
    if failed_tests == 0:
        print("🎉 All tests passed!")
        return 0
    else:
        print("💥 Some tests failed!")
        return 1


def run_specific_test(test_name: str):
    """Run a specific test by name."""
    project_root = Path(__file__).parent
    server_dir = project_root / "server"
    if str(server_dir) not in sys.path:
        sys.path.insert(0, str(server_dir))
    
    os.environ.setdefault("OPENROUTER_API_KEY", "test-key")
    os.environ.setdefault("CONTEXT_OPTIMIZATION_ENABLED", "true")
    
    print(f"🧪 Running specific test: {test_name}")
    
    try:
        result = subprocess.run([
            "bash", "-c", 
            f"source openpoke-env/bin/activate && python -m pytest tests/{test_name} -v --tb=short"
        ], cwd=project_root)
        
        return result.returncode
    except Exception as e:
        print(f"❌ Error running test: {e}")
        return 1


def show_test_coverage():
    """Show test coverage information."""
    project_root = Path(__file__).parent
    server_dir = project_root / "server"
    if str(server_dir) not in sys.path:
        sys.path.insert(0, str(server_dir))
    
    os.environ.setdefault("OPENROUTER_API_KEY", "test-key")
    os.environ.setdefault("CONTEXT_OPTIMIZATION_ENABLED", "true")
    
    print("📊 Generating Test Coverage Report...")
    
    try:
        result = subprocess.run([
            "bash", "-c", 
            "source openpoke-env/bin/activate && python -m pytest tests/test_context_optimizer.py tests/test_context_metrics.py tests/test_agent_integration.py tests/test_context_optimization_integration.py tests/test_context_optimization_api.py --cov=server.services.conversation.context_optimizer --cov=server.services.conversation.context_metrics --cov=server.routes.context_optimization --cov-report=term-missing --cov-report=html:htmlcov"
        ], cwd=project_root)
        
        print("\n📁 Coverage report generated in htmlcov/ directory")
        return result.returncode
    except Exception as e:
        print(f"❌ Error generating coverage: {e}")
        return 1


if __name__ == "__main__":
    if len(sys.argv) > 1:
        command = sys.argv[1]
        if command == "coverage":
            exit_code = show_test_coverage()
        elif command.startswith("test:"):
            test_name = command.split(":", 1)[1]
            exit_code = run_specific_test(test_name)
        else:
            print(f"Unknown command: {command}")
            print("Available commands:")
            print("  coverage - Generate test coverage report")
            print("  test:<name> - Run specific test file")
            exit_code = 1
    else:
        exit_code = run_tests()
    
    sys.exit(exit_code)
