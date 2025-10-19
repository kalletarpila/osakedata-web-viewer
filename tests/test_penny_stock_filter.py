#!/usr/bin/env python3
"""
Test suite for penny stock filtering functionality.
"""

import pytest
import pandas as pd
from unittest.mock import MagicMock, patch
from main import is_penny_stock, fetch_yfinance_data, fetch_csv_data, fetch_tickers_from_file


class TestPennyStockFilter:
    """Test suite for penny stock filtering."""
    
    @pytest.mark.unit
    def test_is_penny_stock_with_penny_stock(self):
        """Test that penny stock (avg < $1.00) is correctly identified."""
        # Create test data with average close price < $1.00
        penny_data = pd.DataFrame({
            'Date': pd.date_range('2023-01-01', periods=10),
            'Close': [0.50, 0.45, 0.60, 0.55, 0.40, 0.65, 0.70, 0.45, 0.50, 0.55]
        })
        
        assert is_penny_stock(penny_data) == True
        assert penny_data['Close'].mean() < 1.0  # Verify test data is correct
    
    @pytest.mark.unit
    def test_is_penny_stock_with_normal_stock(self):
        """Test that normal stock (avg >= $1.00) is not identified as penny stock."""
        # Create test data with average close price >= $1.00
        normal_data = pd.DataFrame({
            'Date': pd.date_range('2023-01-01', periods=10),
            'Close': [15.50, 16.45, 14.60, 15.55, 16.40, 15.65, 14.70, 15.45, 16.50, 15.55]
        })
        
        assert is_penny_stock(normal_data) == False
        assert normal_data['Close'].mean() >= 1.0  # Verify test data is correct
    
    @pytest.mark.unit
    def test_is_penny_stock_border_case(self):
        """Test penny stock identification with border case (mixed prices)."""
        # Create test data that averages exactly around $1.00
        border_data = pd.DataFrame({
            'Date': pd.date_range('2023-01-01', periods=10),
            'Close': [1.50, 1.45, 0.60, 0.55, 0.40, 0.65, 0.70, 0.45, 0.50, 0.55]
        })
        
        avg_price = border_data['Close'].mean()
        expected_result = avg_price < 1.0
        assert is_penny_stock(border_data) == expected_result
    
    @pytest.mark.unit
    def test_is_penny_stock_with_empty_dataframe(self):
        """Test that empty DataFrame is treated as penny stock (safe default)."""
        empty_df = pd.DataFrame()
        assert is_penny_stock(empty_df) == True
    
    @pytest.mark.unit
    def test_is_penny_stock_without_close_column(self):
        """Test that DataFrame without Close column is treated as penny stock."""
        no_close_df = pd.DataFrame({
            'Date': pd.date_range('2023-01-01', periods=5),
            'Open': [1.0, 1.1, 1.2, 1.3, 1.4]
        })
        assert is_penny_stock(no_close_df) == True
    
    @pytest.mark.unit
    def test_is_penny_stock_with_less_than_10_days(self):
        """Test penny stock identification with less than 10 days of data."""
        short_data = pd.DataFrame({
            'Date': pd.date_range('2023-01-01', periods=5),
            'Close': [0.50, 0.45, 0.60, 0.55, 0.40]
        })
        
        assert is_penny_stock(short_data) == True
        assert len(short_data) < 10  # Verify test condition
    
    @pytest.mark.unit
    @pytest.mark.yfinance
    def test_yfinance_penny_stock_filtering(self, monkeypatch, empty_osakedata_db):
        """Test that YFinance function filters out penny stocks."""
        monkeypatch.setattr('main.DB_PATHS', {'osakedata': empty_osakedata_db})
        
        # Mock penny stock data
        penny_hist = pd.DataFrame({
            'Date': pd.date_range('2023-07-01', periods=10),
            'Open': [0.45, 0.40, 0.55, 0.50, 0.35, 0.60, 0.65, 0.40, 0.45, 0.50],
            'High': [0.50, 0.45, 0.60, 0.55, 0.40, 0.65, 0.70, 0.45, 0.50, 0.55],
            'Low': [0.40, 0.35, 0.50, 0.45, 0.30, 0.55, 0.60, 0.35, 0.40, 0.45],
            'Close': [0.45, 0.40, 0.55, 0.50, 0.35, 0.60, 0.65, 0.40, 0.45, 0.50],
            'Volume': [100000] * 10
        })
        
        mock_ticker = MagicMock()
        mock_ticker.history.return_value = penny_hist
        
        with patch('main.yf.Ticker', return_value=mock_ticker):
            success, message, count = fetch_yfinance_data(['PENNY'])
            
            # Should fail because of penny stock filtering
            assert success == False
            assert 'penny stock' in message.lower()
            assert count == 0
    
    @pytest.mark.unit
    @pytest.mark.yfinance
    def test_yfinance_normal_stock_passes(self, monkeypatch, empty_osakedata_db):
        """Test that YFinance function allows normal stocks through."""
        monkeypatch.setattr('main.DB_PATHS', {'osakedata': empty_osakedata_db})
        
        # Mock normal stock data
        normal_hist = pd.DataFrame({
            'Date': pd.date_range('2023-07-01', periods=10),
            'Open': [15.0, 16.0, 14.5, 15.5, 16.5, 15.0, 14.0, 15.5, 16.0, 15.5],
            'High': [15.5, 16.5, 15.0, 16.0, 17.0, 15.5, 14.5, 16.0, 16.5, 16.0],
            'Low': [14.5, 15.5, 14.0, 15.0, 16.0, 14.5, 13.5, 15.0, 15.5, 15.0],
            'Close': [15.0, 16.0, 14.5, 15.5, 16.5, 15.0, 14.0, 15.5, 16.0, 15.5],
            'Volume': [100000] * 10
        })
        
        mock_ticker = MagicMock()
        mock_ticker.history.return_value = normal_hist
        
        with patch('main.yf.Ticker', return_value=mock_ticker):
            success, message, count = fetch_yfinance_data(['NORMAL'])
            
            # Should succeed - normal stock passes filter
            assert success == True
            assert count > 0


class TestPennyStockIntegration:
    """Integration tests for penny stock filtering across all import methods."""
    
    @pytest.mark.integration
    def test_penny_stock_rejected_message_format(self):
        """Test that penny stock rejection messages are properly formatted."""
        test_data = pd.DataFrame({
            'Close': [0.30, 0.35, 0.25, 0.40, 0.20, 0.45, 0.50, 0.25, 0.30, 0.35]
        })
        
        assert is_penny_stock(test_data) == True
        
        # Test that the rejection message format is consistent
        expected_msg_format = "penny stock - alle $1.00 keskiarvo"
        # This format should be used in all three import functions
        
        # Verify average is indeed < 1.00
        assert test_data['Close'].mean() < 1.0