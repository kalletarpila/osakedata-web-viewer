#!/usr/bin/env bash
# 
# Test runner script for Stock Data Viewer
# Provides different test execution modes and reporting options
#

set -e  # Exit on error

# Colors for output
RED='\\033[0;31m'
GREEN='\\033[0;32m'
YELLOW='\\033[1;33m'
BLUE='\\033[0;34m'
NC='\\033[0m' # No Color

# Function to print colored output
print_status() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check if we're in the right directory
if [[ ! -f "main.py" ]]; then
    print_error "This script must be run from the project root directory"
    exit 1
fi

# Check if virtual environment exists
if [[ ! -d ".venv" ]]; then
    print_warning "Virtual environment not found. Creating one..."
    python3 -m venv .venv
fi

# Activate virtual environment
print_status "Activating virtual environment..."
source .venv/bin/activate

# Install/upgrade test dependencies
print_status "Installing test dependencies..."
pip install -r requirements.txt

# Function to run tests with specific markers
run_tests() {
    local test_type="$1"
    local markers="$2" 
    local description="$3"
    
    print_status "Running $description..."
    
    if [[ -n "$markers" ]]; then
        pytest tests/ -m "$markers" -v --tb=short
    else
        pytest tests/ -v --tb=short
    fi
    
    local exit_code=$?
    if [[ $exit_code -eq 0 ]]; then
        print_success "$description completed successfully"
    else
        print_error "$description failed with exit code $exit_code"
        return $exit_code
    fi
}

# Function to run tests with coverage
run_coverage() {
    print_status "Running tests with coverage analysis..."
    
    pytest tests/ \\
        --cov=main \\
        --cov-report=html:htmlcov \\
        --cov-report=term-missing \\
        --cov-report=xml:coverage.xml \\
        -v
    
    local exit_code=$?
    if [[ $exit_code -eq 0 ]]; then
        print_success "Coverage analysis completed"
        print_status "Coverage report saved to htmlcov/index.html"
    else
        print_error "Coverage analysis failed"
        return $exit_code
    fi
}

# Parse command line arguments
case "${1:-all}" in
    "unit")
        run_tests "unit" "unit" "unit tests"
        ;;
    "integration") 
        run_tests "integration" "integration" "integration tests"
        ;;
    "db")
        run_tests "database" "db" "database tests"
        ;;
    "web")
        run_tests "web" "web" "web interface tests"
        ;;
    "performance"|"perf")
        run_tests "performance" "slow" "performance tests"
        ;;
    "quick"|"fast")
        run_tests "quick" "not slow" "quick tests (excluding slow tests)"
        ;;
    "coverage"|"cov")
        run_coverage
        ;;
    "all")
        print_status "Running complete test suite..."
        
        # Run quick tests first
        run_tests "quick" "not slow" "quick tests"
        
        # Then run slow tests if quick tests pass
        if [[ $? -eq 0 ]]; then
            print_status "Quick tests passed, running performance tests..."
            run_tests "performance" "slow" "performance tests"
        fi
        ;;
    "help"|"-h"|"--help")
        echo "Stock Data Viewer Test Runner"
        echo ""
        echo "Usage: $0 [test_type]"
        echo ""
        echo "Test Types:"
        echo "  unit         Run unit tests only"
        echo "  integration  Run integration tests only" 
        echo "  db           Run database tests only"
        echo "  web          Run web interface tests only"
        echo "  performance  Run performance/stress tests (slow)"
        echo "  quick        Run all tests except slow ones"
        echo "  coverage     Run tests with coverage analysis"
        echo "  all          Run complete test suite (default)"
        echo "  help         Show this help message"
        echo ""
        echo "Examples:"
        echo "  $0               # Run all tests"
        echo "  $0 unit          # Run only unit tests"
        echo "  $0 coverage      # Run with coverage report"
        echo "  $0 quick         # Skip slow performance tests"
        exit 0
        ;;
    *)
        print_error "Unknown test type: $1"
        print_status "Use '$0 help' to see available options"
        exit 1
        ;;
esac

# Final status
if [[ $? -eq 0 ]]; then
    print_success "All tests completed successfully! ✅"
else
    print_error "Some tests failed! ❌"
    exit 1
fi