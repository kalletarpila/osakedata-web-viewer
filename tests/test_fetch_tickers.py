"""
Unit and integration tests for Fetch Tickers functionality in main.py

Tests cover:
- fetch_tickers_from_file() function with various scenarios
- /fetch_tickers Flask route JSON API
- File handling and validation
- Error handling for missing files and invalid data
- Rate limiting and progress tracking
- Statistics reporting (processed/success/error counts)
- Ticker file processing with time delays
"""

import pytest
import os
import sqlite3
import pandas as pd
import tempfile
import json
from unittest.mock import patch, MagicMock, mock_open
from datetime import datetime

from main import fetch_tickers_from_file, app


class TestFetchTickersFromFile:
    """Test suite for fetch_tickers_from_file function."""
    
    @pytest.mark.unit
    @pytest.mark.yfinance
    def test_fetch_tickers_from_file_missing_file(self, monkeypatch, empty_osakedata_db):
        """Test with missing tickers.txt file."""
        monkeypatch.setattr('main.DB_PATHS', {'osakedata': empty_osakedata_db})
        
        # Mock a non-existent file
        with patch('os.path.exists', return_value=False):
            success, message, stats = fetch_tickers_from_file()
            assert success is False
            assert "Tickers-tiedostoa ei löytynyt" in message
            assert stats['processed'] == 0
            assert stats['success_count'] == 0
            assert stats['error_count'] == 0
            assert stats['total_saved'] == 0

    @pytest.mark.unit
    @pytest.mark.yfinance
    def test_fetch_tickers_from_file_empty_file(self, monkeypatch, empty_osakedata_db):
        """Test with empty tickers.txt file."""
        monkeypatch.setattr('main.DB_PATHS', {'osakedata': empty_osakedata_db})
        
        with patch('os.path.exists', return_value=True):
            with patch('builtins.open', mock_open(read_data="")):
                success, message, stats = fetch_tickers_from_file()
                assert success is False
                assert "Tickers-tiedosto on tyhjä" in message
                assert stats['processed'] == 0

    @pytest.mark.unit
    @pytest.mark.yfinance
    def test_fetch_tickers_from_file_whitespace_only(self, monkeypatch, empty_osakedata_db):
        """Test with file containing only whitespace."""
        monkeypatch.setattr('main.DB_PATHS', {'osakedata': empty_osakedata_db})
        
        whitespace_content = "   \n  \t  \n   "
        
        with patch('os.path.exists', return_value=True):
            with patch('builtins.open', mock_open(read_data=whitespace_content)):
                success, message, stats = fetch_tickers_from_file()
                assert success is False
                assert "Tickers-tiedosto on tyhjä" in message

    @pytest.mark.unit
    @pytest.mark.yfinance
    def test_fetch_tickers_from_file_file_read_error(self, monkeypatch, empty_osakedata_db):
        """Test file read permission error."""
        monkeypatch.setattr('main.DB_PATHS', {'osakedata': empty_osakedata_db})
        
        with patch('os.path.exists', return_value=True):
            with patch('builtins.open', side_effect=PermissionError("Permission denied")):
                success, message, stats = fetch_tickers_from_file()
                assert success is False
                assert "Virhe tickers-tiedoston lukemisessa" in message
                assert "Permission denied" in message

    @pytest.mark.unit
    @pytest.mark.yfinance
    def test_fetch_tickers_from_file_single_ticker_success(self, monkeypatch, empty_osakedata_db):
        """Test successful processing of single ticker."""
        monkeypatch.setattr('main.DB_PATHS', {'osakedata': empty_osakedata_db})
        
        ticker_content = "TESTFILE1\n"
        
        # Mock YFinance response
        mock_ticker = MagicMock()
        mock_hist = pd.DataFrame({
            'Open': [100.0, 101.0],
            'High': [102.0, 103.0],
            'Low': [99.0, 100.0],
            'Close': [101.0, 102.0],
            'Volume': [1000000, 1100000]
        }, index=[pd.Timestamp('2023-07-01'), pd.Timestamp('2023-07-02')])
        mock_hist.index.name = 'Date'
        mock_ticker.history.return_value = mock_hist
        
        with patch('os.path.exists', return_value=True):
            with patch('builtins.open', mock_open(read_data=ticker_content)):
                with patch('main.yf.Ticker', return_value=mock_ticker):
                    with patch('time.sleep'):  # Skip actual delays in tests
                        success, message, stats = fetch_tickers_from_file()
                        
                        assert success is True
                        assert "Käsitelty 1/1 tickeriä" in message
                        assert "Tallennettu 2 riviä" in message
                        assert stats['processed'] == 1
                        assert stats['success_count'] == 1
                        assert stats['error_count'] == 0
                        assert stats['total_saved'] == 2

    @pytest.mark.unit
    @pytest.mark.yfinance
    def test_fetch_tickers_from_file_multiple_tickers_success(self, monkeypatch, empty_osakedata_db):
        """Test successful processing of multiple tickers."""
        monkeypatch.setattr('main.DB_PATHS', {'osakedata': empty_osakedata_db})
        
        ticker_content = "TESTFILE2\nTESTFILE3\nTESTFILE4\n"
        
        # Mock YFinance response for each ticker
        def mock_ticker_side_effect(ticker):
            mock_ticker = MagicMock()
            mock_hist = pd.DataFrame({
                'Open': [100.0],
                'High': [102.0],
                'Low': [99.0],
                'Close': [101.0],
                'Volume': [1000000]
            }, index=[pd.Timestamp('2023-07-01')])
            mock_hist.index.name = 'Date'
            mock_ticker.history.return_value = mock_hist
            return mock_ticker
        
        with patch('os.path.exists', return_value=True):
            with patch('builtins.open', mock_open(read_data=ticker_content)):
                with patch('main.yf.Ticker', side_effect=mock_ticker_side_effect):
                    with patch('time.sleep'):  # Skip actual delays in tests
                        success, message, stats = fetch_tickers_from_file()
                        
                        assert success is True
                        assert "Käsitelty 3/3 tickeriä" in message
                        assert "Tallennettu 3 riviä" in message
                        assert stats['processed'] == 3
                        assert stats['success_count'] == 3
                        assert stats['error_count'] == 0
                        assert stats['total_saved'] == 3

    @pytest.mark.unit
    @pytest.mark.yfinance
    def test_fetch_tickers_from_file_mixed_success_failure(self, monkeypatch, empty_osakedata_db):
        """Test processing with some successful and some failed tickers."""
        monkeypatch.setattr('main.DB_PATHS', {'osakedata': empty_osakedata_db})
        
        ticker_content = "GOODTICK1\nBADTICK1\nGOODTICK2\n"
        
        def mock_ticker_side_effect(ticker):
            mock_ticker = MagicMock()
            if 'GOOD' in ticker:
                # Successful ticker
                mock_hist = pd.DataFrame({
                    'Open': [100.0],
                    'High': [102.0],
                    'Low': [99.0],
                    'Close': [101.0],
                    'Volume': [1000000]
                }, index=[pd.Timestamp('2023-07-01')])
                mock_hist.index.name = 'Date'
                mock_ticker.history.return_value = mock_hist
            else:
                # Failed ticker - no data
                mock_ticker.history.return_value = pd.DataFrame()
            return mock_ticker
        
        with patch('os.path.exists', return_value=True):
            with patch('builtins.open', mock_open(read_data=ticker_content)):
                with patch('main.yf.Ticker', side_effect=mock_ticker_side_effect):
                    with patch('time.sleep'):  # Skip actual delays in tests
                        success, message, stats = fetch_tickers_from_file()
                        
                        assert success is True
                        assert "Käsitelty 3/3 tickeriä" in message
                        assert "Tallennettu 2 riviä" in message
                        assert stats['processed'] == 3
                        assert stats['success_count'] == 2
                        assert stats['error_count'] == 1
                        assert stats['total_saved'] == 2

    @pytest.mark.unit
    @pytest.mark.yfinance
    def test_fetch_tickers_from_file_all_failures(self, monkeypatch, empty_osakedata_db):
        """Test processing where all tickers fail."""
        monkeypatch.setattr('main.DB_PATHS', {'osakedata': empty_osakedata_db})
        
        ticker_content = "INVALID1\nINVALID2\n"
        
        # Mock YFinance to return empty DataFrames (no data)
        mock_ticker = MagicMock()
        mock_ticker.history.return_value = pd.DataFrame()
        
        with patch('os.path.exists', return_value=True):
            with patch('builtins.open', mock_open(read_data=ticker_content)):
                with patch('main.yf.Ticker', return_value=mock_ticker):
                    with patch('time.sleep'):
                        success, message, stats = fetch_tickers_from_file()
                        
                        assert success is True  # Function succeeds even if all tickers fail
                        assert "Käsitelty 2/2 tickeriä" in message
                        assert "Tallennettu 0 riviä" in message
                        assert stats['processed'] == 2
                        assert stats['success_count'] == 0
                        assert stats['error_count'] == 2
                        assert stats['total_saved'] == 0

    @pytest.mark.unit
    @pytest.mark.yfinance
    def test_fetch_tickers_from_file_yfinance_exception(self, monkeypatch, empty_osakedata_db):
        """Test handling of YFinance API exceptions."""
        monkeypatch.setattr('main.DB_PATHS', {'osakedata': empty_osakedata_db})
        
        ticker_content = "EXCEPTION1\n"
        
        # Mock YFinance to raise an exception
        with patch('os.path.exists', return_value=True):
            with patch('builtins.open', mock_open(read_data=ticker_content)):
                with patch('main.yf.Ticker', side_effect=Exception("YFinance API error")):
                    with patch('time.sleep'):
                        success, message, stats = fetch_tickers_from_file()
                        
                        assert success is True
                        assert "Käsitelty 1/1 tickeriä" in message
                        assert stats['processed'] == 1
                        assert stats['success_count'] == 0
                        assert stats['error_count'] == 1

    @pytest.mark.unit
    @pytest.mark.yfinance
    def test_fetch_tickers_from_file_database_error(self, monkeypatch):
        """Test database connection errors."""
        # Use invalid database path
        monkeypatch.setattr('main.DB_PATHS', {'osakedata': '/invalid/path/database.db'})
        
        ticker_content = "TESTDB1\n"
        
        with patch('os.path.exists', return_value=True):
            with patch('builtins.open', mock_open(read_data=ticker_content)):
                success, message, stats = fetch_tickers_from_file()
                
                assert success is False
                assert "Tietokantavirhe" in message
                assert stats['processed'] == 0

    @pytest.mark.unit
    @pytest.mark.yfinance 
    def test_fetch_tickers_from_file_case_normalization(self, monkeypatch, empty_osakedata_db):
        """Test that tickers are converted to uppercase."""
        monkeypatch.setattr('main.DB_PATHS', {'osakedata': empty_osakedata_db})
        
        ticker_content = "testcase1\nTESTCASE2\nTestCase3\n"
        
        mock_ticker = MagicMock()
        mock_hist = pd.DataFrame({
            'Open': [100.0],
            'High': [102.0],
            'Low': [99.0],
            'Close': [101.0],
            'Volume': [1000000]
        }, index=[pd.Timestamp('2023-07-01')])
        mock_hist.index.name = 'Date'
        mock_ticker.history.return_value = mock_hist
        
        with patch('os.path.exists', return_value=True):
            with patch('builtins.open', mock_open(read_data=ticker_content)):
                with patch('main.yf.Ticker', return_value=mock_ticker) as mock_yf:
                    with patch('time.sleep'):
                        success, message, stats = fetch_tickers_from_file()
                        
                        # Verify all tickers were called in uppercase
                        call_args = [call[0][0] for call in mock_yf.call_args_list]
                        assert 'TESTCASE1' in call_args
                        assert 'TESTCASE2' in call_args
                        assert 'TESTCASE3' in call_args

    @pytest.mark.unit
    @pytest.mark.yfinance
    def test_fetch_tickers_from_file_duplicate_prevention(self, monkeypatch, isolated_db):
        """Test that duplicate data is not inserted."""
        monkeypatch.setattr('main.DB_PATHS', {'osakedata': isolated_db, 'analysis': isolated_db})
        
        # Insert existing data
        with sqlite3.connect(isolated_db) as conn:
            cursor = conn.cursor()
            cursor.execute("""
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
            """)
            cursor.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_osake_pvm ON osakedata(osake, pvm)")
            cursor.execute("""
                INSERT INTO osakedata (osake, pvm, open, high, low, close, volume)
                VALUES ('DUPTEST', '2023-07-01', 100.0, 102.0, 99.0, 101.0, 1000000)
            """)
            conn.commit()
        
        ticker_content = "DUPTEST\n"
        
        # Mock YFinance to return the same data
        mock_ticker = MagicMock()
        mock_hist = pd.DataFrame({
            'Open': [100.0],
            'High': [102.0],
            'Low': [99.0],
            'Close': [101.0],
            'Volume': [1000000]
        }, index=[pd.Timestamp('2023-07-01')])
        mock_hist.index.name = 'Date'
        mock_ticker.history.return_value = mock_hist
        
        with patch('os.path.exists', return_value=True):
            with patch('builtins.open', mock_open(read_data=ticker_content)):
                with patch('main.yf.Ticker', return_value=mock_ticker):
                    with patch('time.sleep'):
                        success, message, stats = fetch_tickers_from_file()
                        
                        assert success is True
                        assert stats['processed'] == 1
                        assert stats['total_saved'] == 0  # No new rows saved

    @pytest.mark.unit
    @pytest.mark.yfinance
    def test_fetch_tickers_from_file_nan_handling(self, monkeypatch, empty_osakedata_db):
        """Test that rows with NaN values are skipped."""
        monkeypatch.setattr('main.DB_PATHS', {'osakedata': empty_osakedata_db})
        
        ticker_content = "NANTEST\n"
        
        # Mock YFinance to return data with NaN values
        mock_ticker = MagicMock()
        mock_hist = pd.DataFrame({
            'Open': [100.0, float('nan')],
            'High': [102.0, 103.0],
            'Low': [99.0, 100.0],
            'Close': [101.0, 102.0],
            'Volume': [1000000, 1100000]
        }, index=[pd.Timestamp('2023-07-01'), pd.Timestamp('2023-07-02')])
        mock_hist.index.name = 'Date'
        mock_ticker.history.return_value = mock_hist
        
        with patch('os.path.exists', return_value=True):
            with patch('builtins.open', mock_open(read_data=ticker_content)):
                with patch('main.yf.Ticker', return_value=mock_ticker):
                    with patch('time.sleep'):
                        success, message, stats = fetch_tickers_from_file()
                        
                        assert success is True
                        assert stats['total_saved'] == 1  # Only 1 row saved (NaN row skipped)

    @pytest.mark.slow
    @pytest.mark.integration
    def test_fetch_tickers_from_file_rate_limiting_delays(self, monkeypatch, empty_osakedata_db):
        """Test that rate limiting delays are applied correctly."""
        monkeypatch.setattr('main.DB_PATHS', {'osakedata': empty_osakedata_db})
        
        ticker_content = "DELAY1\nDELAY2\nDELAY3\n"
        
        mock_ticker = MagicMock()
        mock_ticker.history.return_value = pd.DataFrame()  # Empty to speed up test
        
        sleep_calls = []
        
        def mock_sleep(seconds):
            sleep_calls.append(seconds)
        
        with patch('os.path.exists', return_value=True):
            with patch('builtins.open', mock_open(read_data=ticker_content)):
                with patch('main.yf.Ticker', return_value=mock_ticker):
                    with patch('time.sleep', side_effect=mock_sleep):
                        success, message, stats = fetch_tickers_from_file()
                        
                        # Should have 2 sleep calls (1 second each, after first 2 tickers)
                        assert len(sleep_calls) == 2
                        assert all(delay == 1 for delay in sleep_calls)


class TestFetchTickersRoute:
    """Test suite for /fetch_tickers Flask route."""
    
    @pytest.mark.integration
    @pytest.mark.web
    def test_fetch_tickers_route_missing_file(self, app_with_test_db):
        """Test route when tickers.txt file is missing."""
        app.config['TESTING'] = True
        with app.test_client() as client:
            with patch('os.path.exists', return_value=False):
                response = client.post('/fetch_tickers')
                
                assert response.status_code == 200
                data = json.loads(response.get_data(as_text=True))
                assert data['success'] is False
                assert "Tickers-tiedostoa ei löytynyt" in data['message']

    @pytest.mark.integration
    @pytest.mark.web
    def test_fetch_tickers_route_empty_file(self, app_with_test_db):
        """Test route with empty tickers.txt file."""
        app.config['TESTING'] = True
        with app.test_client() as client:
            with patch('os.path.exists', return_value=True):
                with patch('builtins.open', mock_open(read_data="")):
                    response = client.post('/fetch_tickers')
                    
                    assert response.status_code == 200
                    data = json.loads(response.get_data(as_text=True))
                    assert data['success'] is False
                    assert "Tickers-tiedosto on tyhjä" in data['message']

    @pytest.mark.integration
    @pytest.mark.web
    def test_fetch_tickers_route_file_read_error(self, app_with_test_db):
        """Test route with file read permission error."""
        app.config['TESTING'] = True
        with app.test_client() as client:
            with patch('os.path.exists', return_value=True):
                with patch('builtins.open', side_effect=PermissionError("Access denied")):
                    response = client.post('/fetch_tickers')
                    
                    assert response.status_code == 200
                    data = json.loads(response.get_data(as_text=True))
                    assert data['success'] is False
                    assert "Virhe tickers-tiedoston lukemisessa" in data['message']
                    assert "Access denied" in data['message']

    @pytest.mark.integration
    @pytest.mark.web
    def test_fetch_tickers_route_success_single_ticker(self, isolated_db, monkeypatch):
        """Test successful ticker processing via route."""
        monkeypatch.setattr('main.DB_PATHS', {'osakedata': isolated_db, 'analysis': isolated_db})
        
        # Ensure table exists
        with sqlite3.connect(isolated_db) as conn:
            cursor = conn.cursor()
            cursor.execute("""
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
            """)
            cursor.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_osake_pvm ON osakedata(osake, pvm)")
            conn.commit()
        
        ticker_content = "ROUTETEST1\n"
        
        # Mock YFinance response
        mock_ticker = MagicMock()
        mock_hist = pd.DataFrame({
            'Open': [100.0],
            'High': [102.0],
            'Low': [99.0],
            'Close': [101.0],
            'Volume': [1000000]
        }, index=[pd.Timestamp('2023-07-01')])
        mock_hist.index.name = 'Date'
        mock_ticker.history.return_value = mock_hist
        
        app.config['TESTING'] = True
        with app.test_client() as client:
            with patch('os.path.exists', return_value=True):
                with patch('builtins.open', mock_open(read_data=ticker_content)):
                    with patch('main.yf.Ticker', return_value=mock_ticker):
                        with patch('time.sleep'):  # Skip delays in tests
                            response = client.post('/fetch_tickers')
                            
                            assert response.status_code == 200
                            data = json.loads(response.get_data(as_text=True))
                            assert data['success'] is True
                            assert "Käsitelty 1/1 tickeriä" in data['message']
                            assert data['processed'] == 1
                            assert data['success_count'] == 1
                            assert data['error_count'] == 0

    @pytest.mark.integration
    @pytest.mark.web
    def test_fetch_tickers_route_mixed_results(self, isolated_db, monkeypatch):
        """Test route with mixed successful and failed tickers."""
        monkeypatch.setattr('main.DB_PATHS', {'osakedata': isolated_db, 'analysis': isolated_db})
        
        # Ensure table exists
        with sqlite3.connect(isolated_db) as conn:
            cursor = conn.cursor()
            cursor.execute("""
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
            """)
            cursor.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_osake_pvm ON osakedata(osake, pvm)")
            conn.commit()
        
        ticker_content = "ROUTEGOOD\nROUTEBAD\nROUTEGOOD2\n"
        
        def mock_ticker_side_effect(ticker):
            mock_ticker = MagicMock()
            if 'GOOD' in ticker:
                # Successful ticker
                mock_hist = pd.DataFrame({
                    'Open': [100.0],
                    'High': [102.0],
                    'Low': [99.0],
                    'Close': [101.0],
                    'Volume': [1000000]
                }, index=[pd.Timestamp('2023-07-01')])
                mock_hist.index.name = 'Date'
                mock_ticker.history.return_value = mock_hist
            else:
                # Failed ticker
                mock_ticker.history.return_value = pd.DataFrame()
            return mock_ticker
        
        app.config['TESTING'] = True
        with app.test_client() as client:
            with patch('os.path.exists', return_value=True):
                with patch('builtins.open', mock_open(read_data=ticker_content)):
                    with patch('main.yf.Ticker', side_effect=mock_ticker_side_effect):
                        with patch('time.sleep'):
                            response = client.post('/fetch_tickers')
                            
                            assert response.status_code == 200
                            data = json.loads(response.get_data(as_text=True))
                            assert data['success'] is True
                            assert data['processed'] == 3
                            assert data['success_count'] == 2
                            assert data['error_count'] == 1

    @pytest.mark.integration
    @pytest.mark.web
    def test_fetch_tickers_route_invalid_http_method(self, app_with_test_db):
        """Test route with invalid HTTP method."""
        app.config['TESTING'] = True
        with app.test_client() as client:
            response = client.get('/fetch_tickers')  # GET instead of POST
            assert response.status_code == 405  # Method Not Allowed

    @pytest.mark.integration
    @pytest.mark.web
    def test_fetch_tickers_route_json_response_format(self, app_with_test_db):
        """Test that route returns proper JSON format."""
        app.config['TESTING'] = True
        with app.test_client() as client:
            with patch('os.path.exists', return_value=False):
                response = client.post('/fetch_tickers')
                
                assert response.status_code == 200
                assert response.content_type == 'application/json'
                
                data = json.loads(response.get_data(as_text=True))
                
                # Verify required JSON fields are present
                assert 'success' in data
                assert 'message' in data
                assert isinstance(data['success'], bool)
                assert isinstance(data['message'], str)

    @pytest.mark.integration
    @pytest.mark.web
    def test_fetch_tickers_route_success_statistics(self, isolated_db, monkeypatch):
        """Test that route returns correct statistics on success."""
        monkeypatch.setattr('main.DB_PATHS', {'osakedata': isolated_db, 'analysis': isolated_db})
        
        # Ensure table exists
        with sqlite3.connect(isolated_db) as conn:
            cursor = conn.cursor()
            cursor.execute("""
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
            """)
            cursor.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_osake_pvm ON osakedata(osake, pvm)")
            conn.commit()
        
        ticker_content = "STATTEST\n"
        
        mock_ticker = MagicMock()
        mock_hist = pd.DataFrame({
            'Open': [100.0, 101.0],
            'High': [102.0, 103.0],
            'Low': [99.0, 100.0],
            'Close': [101.0, 102.0],
            'Volume': [1000000, 1100000]
        }, index=[pd.Timestamp('2023-07-01'), pd.Timestamp('2023-07-02')])
        mock_hist.index.name = 'Date'
        mock_ticker.history.return_value = mock_hist
        
        app.config['TESTING'] = True
        with app.test_client() as client:
            with patch('os.path.exists', return_value=True):
                with patch('builtins.open', mock_open(read_data=ticker_content)):
                    with patch('main.yf.Ticker', return_value=mock_ticker):
                        with patch('time.sleep'):
                            response = client.post('/fetch_tickers')
                            
                            assert response.status_code == 200
                            data = json.loads(response.get_data(as_text=True))
                            
                            # Verify all statistics fields are present and correct
                            assert data['success'] is True
                            assert data['processed'] == 1
                            assert data['success_count'] == 1
                            assert data['error_count'] == 0
                            assert 'message' in data

    @pytest.mark.integration
    @pytest.mark.web
    def test_fetch_tickers_route_content_type_handling(self, app_with_test_db):
        """Test route handles different content types correctly."""
        app.config['TESTING'] = True
        with app.test_client() as client:
            # Test with application/x-www-form-urlencoded (default)
            with patch('os.path.exists', return_value=False):
                response = client.post('/fetch_tickers', 
                                     content_type='application/x-www-form-urlencoded')
                assert response.status_code == 200
                
            # Test with no explicit content type
            with patch('os.path.exists', return_value=False):
                response = client.post('/fetch_tickers')
                assert response.status_code == 200