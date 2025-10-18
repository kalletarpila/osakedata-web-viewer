"""
Unit tests for database functions in main.py

Tests cover:
- get_stock_data() with various inputs and database types
- get_available_symbols() for both databases  
- delete_stock_data() with different scenarios
- Error handling for missing/corrupted databases
- Edge cases like empty databases, special characters, etc.
"""

import pytest
import os
import pandas as pd
from unittest.mock import patch, MagicMock

from main import get_stock_data, get_available_symbols, delete_stock_data, get_db_path, get_db_label


class TestDatabaseFunctions:
    """Test suite for core database functions."""
    
    @pytest.mark.unit
    @pytest.mark.db
    def test_get_db_path_valid_types(self):
        """Test get_db_path returns correct paths for valid database types."""
        # Test default osakedata
        assert 'osakedata.db' in get_db_path('osakedata')
        
        # Test analysis database
        assert 'analysis.db' in get_db_path('analysis')
        
        # Test invalid type defaults to osakedata
        # Kun tietokantatyyppiä ei löydy, palautetaan testeidenaikainen dummy-polku
        result = get_db_path('invalid_type')
        assert result == '/tmp/dummy.db'
    
    @pytest.mark.unit
    def test_get_db_label(self):
        """Test database label generation."""
        assert get_db_label('osakedata') == 'Osakedata (OHLCV)'
        assert get_db_label('analysis') == 'Kynttiläkuvioanalyysi'
        assert get_db_label('invalid') == 'Tuntematon'


class TestGetStockData:
    """Test suite for get_stock_data function."""
    
    @pytest.mark.unit
    @pytest.mark.db
    def test_get_stock_data_osakedata_single_exact(self, monkeypatch, test_osakedata_db):
        """Test exact single symbol search in osakedata."""
        monkeypatch.setattr('main.DB_PATHS', {'osakedata': test_osakedata_db})
        
        df, error, found_symbols = get_stock_data(['AAPL'], 'osakedata')
        
        assert error is None
        assert not df.empty
        assert 'AAPL' in found_symbols
        assert len(df) == 3  # 3 AAPL records in test data
        assert all(df['osake'] == 'AAPL')
        
    @pytest.mark.unit
    @pytest.mark.db
    def test_get_stock_data_osakedata_multiple(self, monkeypatch, test_osakedata_db):
        """Test multiple symbol search in osakedata."""
        monkeypatch.setattr('main.DB_PATHS', {'osakedata': test_osakedata_db})
        
        df, error, found_symbols = get_stock_data(['AAPL', 'GOOGL'], 'osakedata')
        
        assert error is None
        assert not df.empty
        assert 'AAPL' in found_symbols
        assert 'GOOGL' in found_symbols
        assert len(found_symbols) == 2
        
    @pytest.mark.unit
    @pytest.mark.db
    def test_get_stock_data_osakedata_partial(self, monkeypatch, test_osakedata_db):
        """Test partial symbol search in osakedata."""
        monkeypatch.setattr('main.DB_PATHS', {'osakedata': test_osakedata_db})
        
        df, error, found_symbols = get_stock_data(['A'], 'osakedata')
        
        assert error is None
        assert not df.empty
        # Should find AAPL, AA, ABC (all starting with 'A')
        expected_symbols = {'AAPL', 'AA', 'ABC'}
        assert expected_symbols.issubset(set(found_symbols))
        
    @pytest.mark.unit
    @pytest.mark.db 
    def test_get_stock_data_analysis_exact(self, monkeypatch, test_analysis_db):
        """Test exact search in analysis database."""
        monkeypatch.setattr('main.DB_PATHS', {'analysis': test_analysis_db, 'osakedata': '/tmp/dummy.db'})
        
        df, error, found_symbols = get_stock_data(['AAPL'], 'analysis')
        
        assert error is None
        assert not df.empty
        assert 'AAPL' in found_symbols
        assert len(df) == 3  # 3 AAPL analysis records
        assert all(df['ticker'] == 'AAPL')
        
    @pytest.mark.unit
    @pytest.mark.db
    def test_get_stock_data_analysis_partial(self, monkeypatch, test_analysis_db):
        """Test partial search in analysis database."""
        monkeypatch.setattr('main.DB_PATHS', {'analysis': test_analysis_db})
        
        df, error, found_symbols = get_stock_data(['A'], 'analysis')
        
        assert error is None
        assert not df.empty
        # Should find AAPL, AA, ABC
        expected_symbols = {'AAPL', 'AA', 'ABC'}
        assert expected_symbols.issubset(set(found_symbols))
        
    @pytest.mark.unit
    @pytest.mark.db
    def test_get_stock_data_nonexistent_symbol(self, monkeypatch, test_osakedata_db):
        """Test search for nonexistent symbol."""
        monkeypatch.setattr('main.DB_PATHS', {'osakedata': test_osakedata_db})
        
        df, error, found_symbols = get_stock_data(['NONEXISTENT'], 'osakedata')
        
        assert df.empty
        assert error is not None
        assert 'Ei löytynyt tietoja hakutermeille: NONEXISTENT' in error
        assert found_symbols == []
        
    @pytest.mark.unit
    @pytest.mark.db
    def test_get_stock_data_empty_database(self, monkeypatch, empty_osakedata_db):
        """Test search in empty database."""
        monkeypatch.setattr('main.DB_PATHS', {'osakedata': empty_osakedata_db})
        
        df, error, found_symbols = get_stock_data(['AAPL'], 'osakedata')
        
        assert df.empty
        assert error is not None
        assert 'Ei löytynyt tietoja hakutermeille: AAPL' in error
        assert found_symbols == []
        
    @pytest.mark.unit
    @pytest.mark.db
    def test_get_stock_data_missing_database(self, monkeypatch):
        """Test search with missing database file."""
        monkeypatch.setattr('main.DB_PATHS', {'osakedata': '/nonexistent/path.db'})
        
        df, error, found_symbols = get_stock_data(['AAPL'], 'osakedata')
        
        assert df.empty
        assert error is not None
        assert 'Tietokanta ei löydy' in error
        assert found_symbols == []
        
    @pytest.mark.unit
    @pytest.mark.db
    def test_get_stock_data_corrupted_database(self, monkeypatch, corrupted_db):
        """Test search with corrupted database."""
        monkeypatch.setattr('main.DB_PATHS', {'osakedata': corrupted_db})
        
        df, error, found_symbols = get_stock_data(['AAPL'], 'osakedata')
        
        assert df.empty
        assert error is not None
        assert 'Virhe tietokannasta hakiessa' in error
        assert found_symbols == []
        
    @pytest.mark.unit
    @pytest.mark.db
    def test_get_stock_data_special_characters(self, monkeypatch, test_osakedata_db):
        """Test search with special characters in symbol."""
        monkeypatch.setattr('main.DB_PATHS', {'osakedata': test_osakedata_db})
        
        df, error, found_symbols = get_stock_data(['XY-Z'], 'osakedata')
        
        assert error is None
        assert not df.empty
        assert 'XY-Z' in found_symbols
        
    @pytest.mark.unit
    @pytest.mark.db
    def test_get_stock_data_case_insensitive(self, monkeypatch, test_osakedata_db):
        """Test that search is case insensitive."""
        monkeypatch.setattr('main.DB_PATHS', {'osakedata': test_osakedata_db})
        
        # Search terms are converted to uppercase in the function
        df, error, found_symbols = get_stock_data(['aapl'], 'osakedata')
        
        assert error is None
        assert not df.empty
        assert 'AAPL' in found_symbols


class TestGetAvailableSymbols:
    """Test suite for get_available_symbols function."""
    
    @pytest.mark.unit
    @pytest.mark.db
    def test_get_available_symbols_osakedata(self, monkeypatch, test_osakedata_db):
        """Test getting symbols from osakedata."""
        monkeypatch.setattr('main.DB_PATHS', {'osakedata': test_osakedata_db})
        
        symbols = get_available_symbols('osakedata')
        
        assert len(symbols) > 0
        assert 'AAPL' in symbols
        assert 'GOOGL' in symbols
        assert 'MSFT' in symbols
        # Should be sorted
        assert symbols == sorted(symbols)
        
    @pytest.mark.unit
    @pytest.mark.db
    def test_get_available_symbols_analysis(self, monkeypatch, test_analysis_db):
        """Test getting symbols from analysis database."""
        monkeypatch.setattr('main.DB_PATHS', {'analysis': test_analysis_db})
        
        symbols = get_available_symbols('analysis')
        
        assert len(symbols) > 0
        assert 'AAPL' in symbols
        assert 'GOOGL' in symbols
        assert 'MSFT' in symbols
        # Should be sorted
        assert symbols == sorted(symbols)
        
    @pytest.mark.unit
    @pytest.mark.db
    def test_get_available_symbols_empty_database(self, monkeypatch, empty_osakedata_db):
        """Test getting symbols from empty database."""
        monkeypatch.setattr('main.DB_PATHS', {'osakedata': empty_osakedata_db})
        
        symbols = get_available_symbols('osakedata')
        
        assert symbols == []
        
    @pytest.mark.unit
    @pytest.mark.db
    def test_get_available_symbols_missing_database(self, monkeypatch):
        """Test getting symbols from missing database."""
        monkeypatch.setattr('main.DB_PATHS', {'osakedata': '/nonexistent/path.db'})
        
        symbols = get_available_symbols('osakedata')
        
        assert symbols == []
        
    @pytest.mark.unit
    @pytest.mark.db
    def test_get_available_symbols_corrupted_database(self, monkeypatch, corrupted_db):
        """Test getting symbols from corrupted database."""
        monkeypatch.setattr('main.DB_PATHS', {'osakedata': corrupted_db})
        
        symbols = get_available_symbols('osakedata')
        
        assert symbols == []


class TestDeleteStockData:
    """Test suite for delete_stock_data function."""
    
    @pytest.mark.unit
    @pytest.mark.db
    def test_delete_stock_data_osakedata_success(self, monkeypatch, test_osakedata_db):
        """Test successful deletion from osakedata."""
        monkeypatch.setattr('main.DB_PATHS', {'osakedata': test_osakedata_db})
        
        # Verify data exists before deletion
        df_before, _, _ = get_stock_data(['TEST'], 'osakedata')
        assert not df_before.empty
        initial_count = len(df_before)
        
        # Delete the data
        success, message, count = delete_stock_data(['TEST'], 'osakedata')
        
        assert success is True
        assert count == initial_count
        assert f'Poistettu {initial_count} riviä symboleille: TEST' in message
        
        # Verify data is gone
        df_after, _, _ = get_stock_data(['TEST'], 'osakedata')
        assert df_after.empty
        
    @pytest.mark.unit
    @pytest.mark.db
    def test_delete_stock_data_analysis_success(self, monkeypatch, test_analysis_db):
        """Test successful deletion from analysis database."""
        monkeypatch.setattr('main.DB_PATHS', {'analysis': test_analysis_db})
        
        # Verify data exists
        df_before, _, _ = get_stock_data(['TEST'], 'analysis')
        assert not df_before.empty
        
        # Delete the data
        success, message, count = delete_stock_data(['TEST'], 'analysis')
        
        assert success is True
        assert count == 1
        assert 'TEST' in message
        
        # Verify deletion
        df_after, _, _ = get_stock_data(['TEST'], 'analysis')
        assert df_after.empty
        
    @pytest.mark.unit
    @pytest.mark.db
    def test_delete_stock_data_multiple_symbols(self, monkeypatch, test_osakedata_db):
        """Test deletion of multiple symbols."""
        monkeypatch.setattr('main.DB_PATHS', {'osakedata': test_osakedata_db})
        
        # Delete multiple symbols
        success, message, count = delete_stock_data(['AA', 'ABC'], 'osakedata')
        
        assert success is True
        assert count >= 2  # At least 2 rows deleted (AA and ABC have 1 row each)
        assert 'AA' in message and 'ABC' in message
        
    @pytest.mark.unit
    @pytest.mark.db
    def test_delete_stock_data_nonexistent_symbol(self, monkeypatch, test_osakedata_db):
        """Test deletion of nonexistent symbol."""
        monkeypatch.setattr('main.DB_PATHS', {'osakedata': test_osakedata_db})
        
        success, message, count = delete_stock_data(['NONEXISTENT'], 'osakedata')
        
        assert success is False
        assert count == 0
        assert 'Ei löytynyt poistettavia rivejä' in message
        
    @pytest.mark.unit
    @pytest.mark.db
    def test_delete_stock_data_missing_database(self, monkeypatch):
        """Test deletion with missing database."""
        monkeypatch.setattr('main.DB_PATHS', {'osakedata': '/nonexistent/path.db'})
        
        success, message, count = delete_stock_data(['AAPL'], 'osakedata')
        
        assert success is False
        assert count == 0
        assert 'Tietokanta ei löydy' in message
        
    @pytest.mark.unit
    @pytest.mark.db
    def test_delete_stock_data_corrupted_database(self, monkeypatch, corrupted_db):
        """Test deletion with corrupted database."""
        monkeypatch.setattr('main.DB_PATHS', {'osakedata': corrupted_db})
        
        success, message, count = delete_stock_data(['AAPL'], 'osakedata')
        
        assert success is False
        assert count == 0
        assert 'Virhe tietojen poistossa' in message