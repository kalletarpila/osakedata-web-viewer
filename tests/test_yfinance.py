"""
Unit and integration tests for YFinance functionality in main.py

Tests cover:
- fetch_yfinance_data() function with various scenarios
- /fetch_yfinance Flask route with different inputs
- Data validation and duplicate prevention
- Error handling for invalid tickers and network issues
- Date range validation (2023-07-01 to 2025-09-30)
"""

import pytest
import os
import sqlite3
import pandas as pd
from unittest.mock import patch, MagicMock
from datetime import datetime

from main import fetch_yfinance_data, app


class TestFetchYfinanceData:
    """Test suite for fetch_yfinance_data function."""
    
    @pytest.mark.unit
    @pytest.mark.yfinance
    def test_fetch_yfinance_data_empty_input(self, monkeypatch, empty_osakedata_db):
        """Test with empty ticker list."""
        monkeypatch.setattr('main.DB_PATHS', {'osakedata': empty_osakedata_db})
        
        # Test empty list
        success, message, count = fetch_yfinance_data([])
        assert success is False
        assert "Ei kelvollisia tickereitä annettu" in message
        assert count == 0
        
        # Test list with empty strings
        success, message, count = fetch_yfinance_data(['', '  ', ''])
        assert success is False
        assert "Ei kelvollisia tickereitä annettu" in message
        assert count == 0
    
    @pytest.mark.unit
    @pytest.mark.yfinance
    def test_fetch_yfinance_data_single_ticker(self, monkeypatch, empty_osakedata_db):
        """Test successful data fetch for single ticker."""
        monkeypatch.setattr('main.DB_PATHS', {'osakedata': empty_osakedata_db})
        
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
        
        with patch('main.yf.Ticker', return_value=mock_ticker):
            success, message, count = fetch_yfinance_data(['TESTTICK1'])
            assert success is True
            assert "Tallennettu 2 riviä" in message
            assert count == 2
    
    @pytest.mark.unit
    @pytest.mark.yfinance
    def test_fetch_yfinance_data_multiple_tickers(self, monkeypatch, empty_osakedata_db):
        """Test successful data fetch for multiple tickers."""
        monkeypatch.setattr('main.DB_PATHS', {'osakedata': empty_osakedata_db})
        
        def mock_ticker_side_effect(ticker):
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
            return mock_ticker
        
        with patch('main.yf.Ticker', side_effect=mock_ticker_side_effect):
            success, message, count = fetch_yfinance_data(['TESTTICK2', 'TESTTICK3'])
            assert success is True
            assert "Tallennettu 4 riviä" in message
            assert count == 4
    
    @pytest.mark.unit
    @pytest.mark.yfinance
    def test_fetch_yfinance_data_invalid_ticker(self, monkeypatch, empty_osakedata_db):
        """Test with invalid ticker that returns no data."""
        monkeypatch.setattr('main.DB_PATHS', {'osakedata': empty_osakedata_db})
        
        with patch('main.yf.Ticker') as mock_ticker:
            # Return empty DataFrame for invalid ticker
            mock_ticker.return_value.history.return_value = pd.DataFrame()
            
            success, message, count = fetch_yfinance_data(['INVALIDTICK'])
            assert success is False
            assert "INVALIDTICK (ei dataa)" in message
            assert count == 0
    
    @pytest.mark.unit
    @pytest.mark.yfinance
    def test_fetch_yfinance_data_mixed_valid_invalid(self, monkeypatch, empty_osakedata_db):
        """Test with mix of valid and invalid tickers."""
        monkeypatch.setattr('main.DB_PATHS', {'osakedata': empty_osakedata_db})
        
        def mock_ticker_side_effect(ticker):
            mock_ticker = MagicMock()
            if ticker == 'VALIDTICK':
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
                # Invalid ticker returns empty DataFrame
                mock_ticker.history.return_value = pd.DataFrame()
            return mock_ticker
        
        with patch('main.yf.Ticker', side_effect=mock_ticker_side_effect):
            success, message, count = fetch_yfinance_data(['VALIDTICK', 'INVALID'])
            assert success is True  # Partial success
            assert "Tallennettu 1 riviä" in message
            assert "INVALID (ei dataa)" in message
            assert count == 1
    
    @pytest.mark.unit
    @pytest.mark.yfinance
    def test_fetch_yfinance_data_nan_values(self, monkeypatch, empty_osakedata_db):
        """Test handling of NaN values in data."""
        monkeypatch.setattr('main.DB_PATHS', {'osakedata': empty_osakedata_db})
        
        with patch('main.yf.Ticker') as mock_ticker:
            # Create DataFrame with NaN values
            mock_hist = pd.DataFrame({
                'Open': [100.0, float('nan'), 102.0],
                'High': [102.0, 104.0, float('nan')],
                'Low': [99.0, 100.0, 101.0],
                'Close': [101.0, 103.0, 102.0],
                'Volume': [1000000, 1100000, 1200000]
            }, index=[
                pd.Timestamp('2023-07-01'),
                pd.Timestamp('2023-07-02'),
                pd.Timestamp('2023-07-03')
            ])
            mock_hist.index.name = 'Date'
            mock_ticker.return_value.history.return_value = mock_hist
            
            success, message, count = fetch_yfinance_data(['AAPL'])
            assert success is True
            assert count == 1  # Only one row without NaN values
    
    @pytest.mark.unit
    @pytest.mark.yfinance
    def test_fetch_yfinance_data_duplicate_prevention(self, monkeypatch, test_osakedata_db):
        """Test that duplicate dates are not inserted."""
        monkeypatch.setattr('main.DB_PATHS', {'osakedata': test_osakedata_db})
        
        # First, add some test data to simulate existing data
        with sqlite3.connect(test_osakedata_db) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO osakedata (osake, pvm, open, high, low, close, volume)
                VALUES ('DUPTEST', '2023-07-01', 100.0, 102.0, 99.0, 101.0, 1000000)
            """)
            conn.commit()
        
        with patch('main.yf.Ticker') as mock_ticker:
            # Return data that includes the existing date
            mock_hist = pd.DataFrame({
                'Open': [100.0, 105.0],
                'High': [102.0, 107.0],
                'Low': [99.0, 104.0],
                'Close': [101.0, 106.0],
                'Volume': [1000000, 1500000]
            }, index=[
                pd.Timestamp('2023-07-01'),  # Duplicate
                pd.Timestamp('2023-07-02')   # New
            ])
            mock_hist.index.name = 'Date'
            mock_ticker.return_value.history.return_value = mock_hist
            
            success, message, count = fetch_yfinance_data(['DUPTEST'])
            assert success is True
            assert count == 1  # Only new date should be inserted
    
    @pytest.mark.unit
    @pytest.mark.yfinance
    def test_fetch_yfinance_data_database_error(self, monkeypatch):
        """Test database connection error handling."""
        # Point to non-existent directory
        monkeypatch.setattr('main.DB_PATHS', {'osakedata': '/nonexistent/path.db'})
        
        success, message, count = fetch_yfinance_data(['AAPL'])
        assert success is False
        assert "Tietokantavirhe" in message
        assert count == 0
    
    @pytest.mark.unit
    @pytest.mark.yfinance
    def test_fetch_yfinance_data_yfinance_exception(self, monkeypatch, empty_osakedata_db):
        """Test YFinance API exception handling."""
        monkeypatch.setattr('main.DB_PATHS', {'osakedata': empty_osakedata_db})
        
        with patch('main.yf.Ticker') as mock_ticker:
            # Simulate YFinance exception
            mock_ticker.return_value.history.side_effect = Exception("Network error")
            
            success, message, count = fetch_yfinance_data(['AAPL'])
            assert success is False
            assert "AAPL (virhe: Network error)" in message
            assert count == 0
    
    @pytest.mark.unit
    @pytest.mark.yfinance
    def test_fetch_yfinance_data_case_handling(self, monkeypatch, empty_osakedata_db):
        """Test ticker case handling (should be converted to uppercase)."""
        monkeypatch.setattr('main.DB_PATHS', {'osakedata': empty_osakedata_db})
        
        with patch('main.yf.Ticker') as mock_ticker:
            mock_hist = pd.DataFrame({
                'Open': [100.0],
                'High': [102.0],
                'Low': [99.0],
                'Close': [101.0],
                'Volume': [1000000]
            }, index=[pd.Timestamp('2023-07-01')])
            mock_hist.index.name = 'Date'
            mock_ticker.return_value.history.return_value = mock_hist
            
            success, message, count = fetch_yfinance_data(['casetest1', '  CASETEST2  '])
            assert success is True
            
            # Verify data was saved with uppercase tickers
            with sqlite3.connect(empty_osakedata_db) as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT DISTINCT osake FROM osakedata ORDER BY osake")
                tickers = [row[0] for row in cursor.fetchall()]
                assert tickers == ['CASETEST1', 'CASETEST2']


class TestYfinanceFlaskRoute:
    """Test suite for /fetch_yfinance Flask route."""
    
    @pytest.mark.integration
    @pytest.mark.web
    @pytest.mark.yfinance
    def test_fetch_yfinance_route_success(self, app_with_test_db):
        """Test successful YFinance fetch via web interface."""
        with patch('main.yf.Ticker') as mock_ticker:
            mock_hist = pd.DataFrame({
                'Open': [100.0],
                'High': [102.0],
                'Low': [99.0],
                'Close': [101.0],
                'Volume': [1000000]
            }, index=[pd.Timestamp('2023-07-01')])
            mock_hist.index.name = 'Date'
            mock_ticker.return_value.history.return_value = mock_hist
            
            response = app_with_test_db.post('/fetch_yfinance', data={
                'tickers': 'TESTFLASK1'
            })
            
            assert response.status_code == 200
            assert 'Tallennettu 1 riviä' in response.get_data(as_text=True)
    
    @pytest.mark.integration
    @pytest.mark.web
    @pytest.mark.yfinance
    def test_fetch_yfinance_route_empty_input(self, app_with_test_db):
        """Test YFinance route with empty input."""
        response = app_with_test_db.post('/fetch_yfinance', data={
            'tickers': ''
        })
        
        assert response.status_code == 200
        assert 'Anna vähintään yksi ticker-symboli' in response.get_data(as_text=True)
    
    @pytest.mark.integration
    @pytest.mark.web
    @pytest.mark.yfinance
    def test_fetch_yfinance_route_whitespace_input(self, app_with_test_db):
        """Test YFinance route with whitespace-only input."""
        response = app_with_test_db.post('/fetch_yfinance', data={
            'tickers': '   \t\n  '
        })
        
        assert response.status_code == 200
        assert 'Anna vähintään yksi ticker-symboli' in response.get_data(as_text=True)
    
    @pytest.mark.integration
    @pytest.mark.web
    @pytest.mark.yfinance
    def test_fetch_yfinance_route_multiple_tickers(self, app_with_test_db):
        """Test YFinance route with multiple comma-separated tickers."""
        with patch('main.yf.Ticker') as mock_ticker:
            mock_hist = pd.DataFrame({
                'Open': [100.0],
                'High': [102.0],
                'Low': [99.0],
                'Close': [101.0],
                'Volume': [1000000]
            }, index=[pd.Timestamp('2023-07-01')])
            mock_hist.index.name = 'Date'
            mock_ticker.return_value.history.return_value = mock_hist
            
            response = app_with_test_db.post('/fetch_yfinance', data={
                'tickers': 'TESTFLASK2, TESTFLASK3, TESTFLASK4'
            })
            
            assert response.status_code == 200
            assert 'Tallennettu 3 riviä' in response.get_data(as_text=True)
    
    @pytest.mark.integration
    @pytest.mark.web
    @pytest.mark.yfinance
    def test_fetch_yfinance_route_invalid_ticker(self, app_with_test_db):
        """Test YFinance route with invalid ticker."""
        with patch('main.yf.Ticker') as mock_ticker:
            # Return empty DataFrame for invalid ticker
            mock_ticker.return_value.history.return_value = pd.DataFrame()
            
            response = app_with_test_db.post('/fetch_yfinance', data={
                'tickers': 'INVALIDFLASK'
            })
            
            assert response.status_code == 200
            response_text = response.get_data(as_text=True)
            assert 'INVALIDFLASK (ei dataa)' in response_text
    
    @pytest.mark.integration
    @pytest.mark.web
    @pytest.mark.yfinance
    def test_fetch_yfinance_route_mixed_tickers(self, app_with_test_db):
        """Test YFinance route with mix of valid and invalid tickers."""
        def mock_ticker_side_effect(ticker):
            mock_ticker = MagicMock()
            if ticker == 'TESTFLASK5':
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
                mock_ticker.history.return_value = pd.DataFrame()
            return mock_ticker
        
        with patch('main.yf.Ticker', side_effect=mock_ticker_side_effect):
            response = app_with_test_db.post('/fetch_yfinance', data={
                'tickers': 'TESTFLASK5, INVALIDFLASK2'
            })
            
            assert response.status_code == 200
            response_text = response.get_data(as_text=True)
            assert 'Tallennettu 1 riviä' in response_text
            assert 'INVALIDFLASK2 (ei dataa)' in response_text
    
    @pytest.mark.integration
    @pytest.mark.web
    @pytest.mark.yfinance
    def test_fetch_yfinance_route_case_insensitive(self, app_with_test_db):
        """Test YFinance route handles case insensitive input."""
        with patch('main.yf.Ticker') as mock_ticker:
            mock_hist = pd.DataFrame({
                'Open': [100.0],
                'High': [102.0],
                'Low': [99.0],
                'Close': [101.0],
                'Volume': [1000000]
            }, index=[pd.Timestamp('2023-07-01')])
            mock_hist.index.name = 'Date'
            mock_ticker.return_value.history.return_value = mock_hist
            
            response = app_with_test_db.post('/fetch_yfinance', data={
                'tickers': 'testflask6, testflask7'
            })
            
            assert response.status_code == 200
            assert 'Tallennettu 2 riviä' in response.get_data(as_text=True)
    
    @pytest.mark.integration
    @pytest.mark.web
    @pytest.mark.yfinance
    def test_fetch_yfinance_route_special_characters(self, app_with_test_db):
        """Test YFinance route with special characters and whitespace."""
        with patch('main.yf.Ticker') as mock_ticker:
            mock_hist = pd.DataFrame({
                'Open': [100.0],
                'High': [102.0],
                'Low': [99.0],
                'Close': [101.0],
                'Volume': [1000000]
            }, index=[pd.Timestamp('2023-07-01')])
            mock_hist.index.name = 'Date'
            mock_ticker.return_value.history.return_value = mock_hist
            
            response = app_with_test_db.post('/fetch_yfinance', data={
                'tickers': '  TESTFLASK8  ,, , TESTFLASK9,  '
            })
            
            assert response.status_code == 200
            # Should handle cleaning and only process valid tickers
            assert 'Tallennettu 2 riviä' in response.get_data(as_text=True)
    
    @pytest.mark.integration
    @pytest.mark.web
    @pytest.mark.yfinance
    def test_fetch_yfinance_route_no_form_data(self, app_with_test_db):
        """Test YFinance route without tickers form field."""
        response = app_with_test_db.post('/fetch_yfinance', data={})
        
        assert response.status_code == 200
        assert 'Anna vähintään yksi ticker-symboli' in response.get_data(as_text=True)


class TestYfinanceDateRange:
    """Test suite for YFinance date range validation."""
    
    @pytest.mark.unit
    @pytest.mark.yfinance
    def test_date_range_constants(self):
        """Test that date range constants are correct."""
        from main import fetch_yfinance_data
        import inspect
        
        # Check source code for date constants
        source = inspect.getsource(fetch_yfinance_data)
        assert "2023-07-01" in source
        assert "2025-09-30" in source
    
    @pytest.mark.unit
    @pytest.mark.yfinance
    def test_yfinance_date_range_mock(self, monkeypatch, empty_osakedata_db):
        """Test that YFinance is called with correct date range."""
        monkeypatch.setattr('main.DB_PATHS', {'osakedata': empty_osakedata_db})
        
        with patch('main.yf.Ticker') as mock_ticker:
            mock_hist = pd.DataFrame()  # Empty to avoid processing
            mock_ticker.return_value.history.return_value = mock_hist
            
            fetch_yfinance_data(['AAPL'])
            
            # Verify yf.Ticker().history was called with correct dates
            mock_ticker.return_value.history.assert_called_once_with(
                start="2023-07-01", 
                end="2025-09-30"
            )


class TestYfinanceIntegration:
    """Integration tests for YFinance functionality with real scenarios."""
    
    @pytest.mark.integration
    @pytest.mark.yfinance
    def test_yfinance_database_integration(self, monkeypatch, empty_osakedata_db):
        """Test full integration from YFinance to database."""
        monkeypatch.setattr('main.DB_PATHS', {'osakedata': empty_osakedata_db})
        
        with patch('main.yf.Ticker') as mock_ticker:
            # Create realistic test data
            mock_hist = pd.DataFrame({
                'Open': [150.0, 151.0, 149.0],
                'High': [152.0, 153.0, 151.0],
                'Low': [149.0, 150.0, 148.0],
                'Close': [151.0, 152.0, 150.0],
                'Volume': [50000000, 52000000, 48000000]
            }, index=[
                pd.Timestamp('2023-07-01'),
                pd.Timestamp('2023-07-02'),
                pd.Timestamp('2023-07-03')
            ])
            mock_hist.index.name = 'Date'
            mock_ticker.return_value.history.return_value = mock_hist
            
            # Fetch data
            success, message, count = fetch_yfinance_data(['INTEGTEST1'])
            
            assert success is True
            assert count == 3
            
            # Verify data in database
            with sqlite3.connect(empty_osakedata_db) as conn:
                df = pd.read_sql_query("SELECT * FROM osakedata WHERE osake = 'INTEGTEST1' ORDER BY pvm", conn)
                
                assert len(df) == 3
                assert df.iloc[0]['osake'] == 'INTEGTEST1'
                assert df.iloc[0]['pvm'] == '2023-07-01'
                assert df.iloc[0]['open'] == 150.0
                assert df.iloc[0]['high'] == 152.0
                assert df.iloc[0]['low'] == 149.0
                assert df.iloc[0]['close'] == 151.0
                assert df.iloc[0]['volume'] == 50000000
    
    @pytest.mark.integration
    @pytest.mark.yfinance
    def test_yfinance_symbols_update(self, monkeypatch, empty_osakedata_db):
        """Test that available symbols are updated after YFinance fetch."""
        from main import get_available_symbols
        
        monkeypatch.setattr('main.DB_PATHS', {'osakedata': empty_osakedata_db})
        
        # Initially no symbols
        symbols_before = get_available_symbols('osakedata')
        assert len(symbols_before) == 0
        
        with patch('main.yf.Ticker') as mock_ticker:
            mock_hist = pd.DataFrame({
                'Open': [100.0],
                'High': [102.0],
                'Low': [99.0],
                'Close': [101.0],
                'Volume': [1000000]
            }, index=[pd.Timestamp('2023-07-01')])
            mock_hist.index.name = 'Date'
            mock_ticker.return_value.history.return_value = mock_hist
            
            # Fetch data for multiple tickers
            fetch_yfinance_data(['INTEGTEST2', 'INTEGTEST3'])
        
        # Symbols should be updated
        symbols_after = get_available_symbols('osakedata')
        assert len(symbols_after) == 2
        assert 'INTEGTEST2' in symbols_after
        assert 'INTEGTEST3' in symbols_after