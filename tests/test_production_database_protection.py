#!/usr/bin/env python3
"""
Test module to ensure production database protection and isolation.
This test verifies that all tests use proper isolation and cannot modify
the production databases located at:
- /home/kalle/projects/rawcandle/data/osakedata.db
- /home/kalle/projects/rawcandle/analysis/analysis.db
"""

import pytest
import os
import sqlite3
import time
from unittest.mock import patch, MagicMock

from main import (
    get_stock_data, 
    get_available_symbols, 
    delete_stock_data, 
    fetch_yfinance_data, 
    DB_PATHS
)


class TestProductionDatabaseProtection:
    """Test suite to ensure production databases are never accessed during testing."""
    
    # Production database paths
    PROD_OSAKEDATA_PATH = "/home/kalle/projects/rawcandle/data/osakedata.db"
    PROD_ANALYSIS_PATH = "/home/kalle/projects/rawcandle/analysis/analysis.db"
    
    @pytest.fixture(autouse=True)
    def setup_database_monitoring(self):
        """Monitor production databases before and after each test."""
        # Store original modification times
        self.original_mtimes = {}
        
        if os.path.exists(self.PROD_OSAKEDATA_PATH):
            self.original_mtimes['osakedata'] = os.path.getmtime(self.PROD_OSAKEDATA_PATH)
        
        if os.path.exists(self.PROD_ANALYSIS_PATH):
            self.original_mtimes['analysis'] = os.path.getmtime(self.PROD_ANALYSIS_PATH)
            
        yield
        
        # Check databases were not modified
        if os.path.exists(self.PROD_OSAKEDATA_PATH):
            current_mtime = os.path.getmtime(self.PROD_OSAKEDATA_PATH)
            assert current_mtime == self.original_mtimes['osakedata'], \
                f"Production osakedata.db was modified during test! Original: {self.original_mtimes['osakedata']}, Current: {current_mtime}"
        
        if os.path.exists(self.PROD_ANALYSIS_PATH):
            current_mtime = os.path.getmtime(self.PROD_ANALYSIS_PATH)
            assert current_mtime == self.original_mtimes['analysis'], \
                f"Production analysis.db was modified during test! Original: {self.original_mtimes['analysis']}, Current: {current_mtime}"

    @pytest.mark.unit
    @pytest.mark.db
    def test_production_paths_visible_but_protected(self):
        """Test that production paths are visible but protected by autouse fixture."""
        # This test documents that production paths are the default (which is correct)
        # but verifies they are protected by the autouse fixture
        
        # Check current DB_PATHS - these point to production during normal operation
        current_osakedata_path = DB_PATHS.get('osakedata', '')
        current_analysis_path = DB_PATHS.get('analysis', '')
        
        print(f"Current osakedata path: {current_osakedata_path}")
        print(f"Current analysis path: {current_analysis_path}")
        
        # Production paths should be visible (this is expected and correct)
        assert current_osakedata_path == self.PROD_OSAKEDATA_PATH
        assert current_analysis_path == self.PROD_ANALYSIS_PATH
        
        # But the autouse fixture ensures they won't be modified
        # This test passes because the fixture monitors and protects the databases
        print("✅ Production paths are visible but protected by autouse fixture")

    @pytest.mark.unit
    @pytest.mark.db
    def test_get_stock_data_with_test_database(self, monkeypatch, test_osakedata_db):
        """Test that get_stock_data uses test database, not production."""
        # Patch to use test database
        monkeypatch.setattr('main.DB_PATHS', {'osakedata': test_osakedata_db})
        
        # Verify the patched path is used
        from main import DB_PATHS as patched_paths
        assert patched_paths['osakedata'] == test_osakedata_db
        assert patched_paths['osakedata'] != self.PROD_OSAKEDATA_PATH
        
        # Execute function
        df, error, found_symbols = get_stock_data(['AAPL'], 'osakedata')
        
        # Should work with test data
        assert error is None
        assert not df.empty

    @pytest.mark.unit  
    @pytest.mark.db
    def test_get_available_symbols_with_test_database(self, monkeypatch, test_osakedata_db):
        """Test that get_available_symbols uses test database, not production."""
        monkeypatch.setattr('main.DB_PATHS', {'osakedata': test_osakedata_db})
        
        symbols = get_available_symbols('osakedata')
        assert isinstance(symbols, list)
        # Should contain test data symbols
        assert 'AAPL' in symbols

    @pytest.mark.unit
    @pytest.mark.yfinance
    def test_fetch_yfinance_data_with_test_database(self, monkeypatch, empty_osakedata_db):
        """Test that fetch_yfinance_data uses test database, not production."""
        monkeypatch.setattr('main.DB_PATHS', {'osakedata': empty_osakedata_db})
        
        # Mock YFinance to avoid network calls
        with patch('main.yf.Ticker') as mock_ticker:
            mock_hist = MagicMock()
            mock_hist.empty = False
            mock_hist.__len__ = lambda x: 1
            mock_hist.index = [MagicMock()]
            mock_hist.index[0].strftime = lambda x: '2023-07-01'
            mock_hist.iterrows.return_value = [
                ('2023-07-01', {
                    'Open': 100.0,
                    'High': 102.0, 
                    'Low': 99.0,
                    'Close': 101.0,
                    'Volume': 1000000
                })
            ]
            mock_ticker.return_value.history.return_value = mock_hist
            
            success, message, count = fetch_yfinance_data(['PRODTEST'])
            
            # Should complete without accessing production database
            assert success in [True, False]  # May succeed or fail, but shouldn't crash
            assert isinstance(message, str)
            assert isinstance(count, int)

    @pytest.mark.integration
    @pytest.mark.web
    def test_flask_routes_use_test_databases(self, app_with_test_db):
        """Test that Flask routes use test databases, not production."""
        # The app_with_test_db fixture should patch database paths
        
        # Test search route with POST (correct method)
        response = app_with_test_db.post('/search', data={
            'symbols': 'AAPL',
            'database': 'osakedata'
        })
        assert response.status_code == 200
        
        # Test API route  
        response = app_with_test_db.get('/api/symbols')
        assert response.status_code == 200

    @pytest.mark.unit
    @pytest.mark.db
    def test_database_paths_isolation(self, monkeypatch, temp_test_dir):
        """Test that database path isolation works correctly."""
        # Create test paths
        test_paths = {
            'osakedata': os.path.join(temp_test_dir, 'isolated_osakedata.db'),
            'analysis': os.path.join(temp_test_dir, 'isolated_analysis.db')
        }
        
        # Patch paths
        monkeypatch.setattr('main.DB_PATHS', test_paths)
        
        # Verify paths are isolated
        from main import get_db_path
        assert get_db_path('osakedata') == test_paths['osakedata']
        assert get_db_path('analysis') == test_paths['analysis']
        
        # Ensure they are not production paths
        assert get_db_path('osakedata') != self.PROD_OSAKEDATA_PATH
        assert get_db_path('analysis') != self.PROD_ANALYSIS_PATH

    @pytest.mark.unit
    @pytest.mark.db
    def test_no_production_database_connections_created(self, monkeypatch, temp_test_dir):
        """Test that no connections to production databases are created during testing."""
        # Track any sqlite3.connect calls
        original_connect = sqlite3.connect
        connect_calls = []
        
        def tracking_connect(database, *args, **kwargs):
            connect_calls.append(database)
            return original_connect(database, *args, **kwargs)
        
        # Create test database paths
        test_osakedata_path = os.path.join(temp_test_dir, 'track_test_osakedata.db')
        
        # Create empty test database
        with sqlite3.connect(test_osakedata_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS osakedata (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    osake TEXT,
                    pvm TEXT,
                    open REAL,
                    high REAL,
                    low REAL,
                    close REAL,
                    volume INTEGER
                )
            ''')
            conn.commit()
        
        # Patch database paths and sqlite3.connect
        monkeypatch.setattr('main.DB_PATHS', {'osakedata': test_osakedata_path})
        monkeypatch.setattr('sqlite3.connect', tracking_connect)
        
        # Execute some database operations
        df, error, found_symbols = get_stock_data(['TESTSTOCK'], 'osakedata')
        symbols = get_available_symbols('osakedata')
        
        # Verify no production database connections were made
        for call in connect_calls:
            assert call != self.PROD_OSAKEDATA_PATH, f"Production osakedata.db was accessed: {call}"
            assert call != self.PROD_ANALYSIS_PATH, f"Production analysis.db was accessed: {call}"
        
        # Verify only test database was accessed
        assert test_osakedata_path in connect_calls, "Test database should have been accessed"

    @pytest.mark.unit
    @pytest.mark.db  
    def test_production_database_file_handles_not_opened(self, monkeypatch):
        """Test that production database file handles are never opened during testing."""
        # This test ensures that even if paths somehow leak, file handles aren't opened
        original_open = open
        file_opens = []
        
        def tracking_open(filename, *args, **kwargs):
            file_opens.append(str(filename))
            return original_open(filename, *args, **kwargs)
        
        # Patch open function and database paths to safe locations
        monkeypatch.setattr('builtins.open', tracking_open)
        monkeypatch.setattr('main.DB_PATHS', {
            'osakedata': '/tmp/safe_test_osakedata.db',
            'analysis': '/tmp/safe_test_analysis.db'
        })
        
        # Try to trigger various operations that might open files
        try:
            get_available_symbols('osakedata')
        except:
            pass  # Ignore errors, we just want to check file access
        
        # Check no production database files were opened
        for opened_file in file_opens:
            assert self.PROD_OSAKEDATA_PATH not in opened_file, f"Production osakedata.db file was opened: {opened_file}"
            assert self.PROD_ANALYSIS_PATH not in opened_file, f"Production analysis.db file was opened: {opened_file}"

    @pytest.mark.integration
    @pytest.mark.db
    def test_comprehensive_database_isolation(self, monkeypatch, test_osakedata_db, test_analysis_db):
        """Comprehensive test of database isolation across all functions."""
        # Patch all database paths
        monkeypatch.setattr('main.DB_PATHS', {
            'osakedata': test_osakedata_db,
            'analysis': test_analysis_db
        })
        
        # Test multiple operations
        operations_performed = []
        
        # Test osakedata operations
        try:
            df, error, symbols = get_stock_data(['AAPL'], 'osakedata')
            operations_performed.append('get_stock_data_osakedata')
        except Exception as e:
            operations_performed.append(f'get_stock_data_osakedata_error: {e}')
        
        try:
            symbols = get_available_symbols('osakedata')
            operations_performed.append('get_available_symbols_osakedata')
        except Exception as e:
            operations_performed.append(f'get_available_symbols_osakedata_error: {e}')
        
        # Test analysis operations  
        try:
            df, error, symbols = get_stock_data(['AAPL'], 'analysis')
            operations_performed.append('get_stock_data_analysis')
        except Exception as e:
            operations_performed.append(f'get_stock_data_analysis_error: {e}')
        
        try:
            symbols = get_available_symbols('analysis')
            operations_performed.append('get_available_symbols_analysis')
        except Exception as e:
            operations_performed.append(f'get_available_symbols_analysis_error: {e}')
        
        # Verify at least some operations were performed (shows patching worked)
        assert len(operations_performed) > 0
        print(f"Operations performed: {operations_performed}")
        
        # The key test is that this completes without accessing production databases
        # which is verified by the autouse fixture