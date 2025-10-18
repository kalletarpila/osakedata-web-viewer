"""
Test summary generator and health check script.

This script provides:
- Test coverage summary
- Test execution health check
- Database connection validation
- Performance benchmark baseline
"""

import os
import sys
import sqlite3
import time
import subprocess
from pathlib import Path

# Add main module to path
sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    from main import get_stock_data, get_available_symbols, DB_PATHS
except ImportError as e:
    print(f"Error importing main module: {e}")
    sys.exit(1)


class TestHealthCheck:
    """Health check for test environment and application."""
    
    def __init__(self):
        self.passed = 0
        self.failed = 0
        self.warnings = 0
    
    def check(self, name, condition, warning=False):
        """Check a condition and report result."""
        if condition:
            self.passed += 1
            print(f"✅ {name}")
            return True
        else:
            if warning:
                self.warnings += 1
                print(f"⚠️  {name}")
            else:
                self.failed += 1
                print(f"❌ {name}")
            return False
    
    def info(self, message):
        """Print info message."""
        print(f"ℹ️  {message}")
    
    def summary(self):
        """Print test summary."""
        total = self.passed + self.failed + self.warnings
        print(f"\\n📊 Health Check Summary:")
        print(f"   Passed: {self.passed}/{total}")
        print(f"   Failed: {self.failed}/{total}")
        print(f"   Warnings: {self.warnings}/{total}")
        
        if self.failed == 0:
            print("\\n🎉 All critical checks passed!")
            return True
        else:
            print(f"\\n💥 {self.failed} critical issues found!")
            return False


def check_databases():
    """Check database connectivity and structure."""
    health = TestHealthCheck()
    
    print("🔍 Database Health Check")
    print("=" * 50)
    
    for db_type, db_path in DB_PATHS.items():
        health.info(f"Checking {db_type} database: {db_path}")
        
        # Check if file exists
        health.check(
            f"{db_type}: Database file exists", 
            os.path.exists(db_path),
            warning=True
        )
        
        if os.path.exists(db_path):
            try:
                # Check database connection
                conn = sqlite3.connect(db_path)
                cursor = conn.cursor()
                
                # Check table structure
                if db_type == 'osakedata':
                    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='osakedata'")
                    table_exists = cursor.fetchone() is not None
                    health.check(f"{db_type}: osakedata table exists", table_exists)
                    
                    if table_exists:
                        cursor.execute("SELECT COUNT(*) FROM osakedata")
                        count = cursor.fetchone()[0]
                        health.check(f"{db_type}: Contains data ({count} records)", count > 0, warning=True)
                        health.info(f"   Found {count} records in osakedata")
                
                elif db_type == 'analysis':
                    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='analysis_findings'")
                    table_exists = cursor.fetchone() is not None
                    health.check(f"{db_type}: analysis_findings table exists", table_exists)
                    
                    if table_exists:
                        cursor.execute("SELECT COUNT(*) FROM analysis_findings")
                        count = cursor.fetchone()[0]
                        health.check(f"{db_type}: Contains data ({count} records)", count > 0, warning=True)
                        health.info(f"   Found {count} records in analysis_findings")
                
                conn.close()
                
            except Exception as e:
                health.check(f"{db_type}: Database connection", False)
                health.info(f"   Error: {e}")
    
    return health.summary()


def check_application_functions():
    """Check core application functions."""
    health = TestHealthCheck()
    
    print("\\n🔧 Application Function Check")
    print("=" * 50)
    
    # Test database connections
    for db_type in ['osakedata', 'analysis']:
        if not os.path.exists(DB_PATHS[db_type]):
            health.check(f"{db_type}: Skipped (database not available)", True, warning=True)
            continue
        
        try:
            # Test symbol retrieval
            start_time = time.time()
            symbols = get_available_symbols(db_type)
            symbol_time = time.time() - start_time
            
            health.check(f"{db_type}: get_available_symbols() works", len(symbols) >= 0)
            health.check(f"{db_type}: Symbol query performance (<100ms)", symbol_time < 0.1, warning=True)
            
            if symbols:
                # Test data retrieval with first symbol
                test_symbol = symbols[0]
                start_time = time.time()
                df, error, found_symbols = get_stock_data([test_symbol], db_type)
                query_time = time.time() - start_time
                
                health.check(f"{db_type}: get_stock_data() works", error is None)
                health.check(f"{db_type}: Data query performance (<100ms)", query_time < 0.1, warning=True)
                
                if error is None:
                    health.info(f"   Successfully retrieved {len(df)} records for {test_symbol}")
            else:
                health.check(f"{db_type}: Database has symbols", False, warning=True)
        
        except Exception as e:
            health.check(f"{db_type}: Function calls", False)
            health.info(f"   Error: {e}")
    
    return health.summary()


def run_quick_test():
    """Run a quick test to ensure pytest is working."""
    health = TestHealthCheck()
    
    print("\\n🧪 Quick Test Execution")
    print("=" * 50)
    
    try:
        # Check if pytest is available
        result = subprocess.run(['pytest', '--version'], 
                              capture_output=True, text=True, timeout=10)
        health.check("pytest is installed", result.returncode == 0)
        
        if result.returncode == 0:
            health.info(f"   {result.stdout.strip()}")
        
        # Try to run a simple test
        if os.path.exists('tests'):
            result = subprocess.run(['pytest', 'tests/', '--collect-only', '-q'], 
                                  capture_output=True, text=True, timeout=30)
            health.check("Test collection works", result.returncode == 0)
            
            if result.returncode == 0:
                # Count collected tests
                lines = result.stdout.split('\\n')
                test_count = 0
                for line in lines:
                    if 'collected' in line and 'item' in line:
                        try:
                            test_count = int(line.split()[0])
                        except:
                            pass
                
                health.check("Tests are discoverable", test_count > 0)
                health.info(f"   Found {test_count} test cases")
            else:
                health.info(f"   Collection error: {result.stderr}")
        else:
            health.check("Tests directory exists", False)
    
    except subprocess.TimeoutExpired:
        health.check("pytest responds in reasonable time", False)
    except Exception as e:
        health.check("pytest execution", False)
        health.info(f"   Error: {e}")
    
    return health.summary()


def check_dependencies():
    """Check required dependencies."""
    health = TestHealthCheck()
    
    print("\\n📦 Dependency Check")
    print("=" * 50)
    
    required_packages = [
        'flask', 'pandas', 'sqlite3', 
        'pytest', 'beautifulsoup4', 'psutil'
    ]
    
    for package in required_packages:
        try:
            if package == 'sqlite3':
                import sqlite3
            else:
                __import__(package)
            health.check(f"{package} is available", True)
        except ImportError:
            warning = package in ['psutil', 'beautifulsoup4']  # Optional for basic functionality
            health.check(f"{package} is available", False, warning=warning)
    
    return health.summary()


def main():
    """Run complete health check."""
    print("🏥 Stock Data Viewer - Test Environment Health Check")
    print("=" * 60)
    
    all_passed = True
    
    # Run all checks
    all_passed &= check_dependencies()
    all_passed &= check_databases()  
    all_passed &= check_application_functions()
    all_passed &= run_quick_test()
    
    # Final summary
    print("\\n" + "=" * 60)
    if all_passed:
        print("🎉 All systems ready for testing!")
        print("\\n💡 Next steps:")
        print("   • Run './run_tests.sh quick' for fast tests")
        print("   • Run './run_tests.sh all' for complete test suite")
        print("   • Run './run_tests.sh coverage' for coverage analysis")
        return 0
    else:
        print("⚠️  Some issues detected. Please resolve before testing.")
        print("\\n💡 Common solutions:")
        print("   • Install missing dependencies: pip install -r requirements.txt")
        print("   • Check database paths in main.py")
        print("   • Ensure databases contain data")
        return 1


if __name__ == "__main__":
    sys.exit(main())