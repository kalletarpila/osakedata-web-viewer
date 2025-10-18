"""
Integration tests for Flask web application routes.

Tests cover:
- GET / (index page)
- POST /search with various parameters
- POST /delete with various scenarios  
- GET /api/symbols endpoint
- Form handling and validation
- Database switching functionality
- Response formats and status codes
"""

import pytest
import json
from bs4 import BeautifulSoup


class TestFlaskRoutes:
    """Test suite for Flask application routes."""
    
    @pytest.mark.integration
    @pytest.mark.web
    def test_index_route_get(self, app_with_test_db):
        """Test GET request to index page."""
        response = app_with_test_db.get('/')
        
        assert response.status_code == 200
        assert b'Stock Data Viewer' in response.data
        assert b'Valitse tietokanta' in response.data
        
        # Parse HTML to check for form elements
        soup = BeautifulSoup(response.data, 'html.parser')
        
        # Check database selector
        db_selector = soup.find('select', {'id': 'db_type'})
        assert db_selector is not None
        
        # Check input field
        ticker_input = soup.find('input', {'id': 'tickers'})
        assert ticker_input is not None
        
        # Check buttons
        search_button = soup.find('button', string=lambda text: '🔍 Hae data' in text if text else False)
        delete_button = soup.find('button', string=lambda text: '🗑️ Poista data' in text if text else False)
        assert search_button is not None
        assert delete_button is not None


class TestSearchRoute:
    """Test suite for /search route."""
    
    @pytest.mark.integration
    @pytest.mark.web
    def test_search_route_osakedata_single_symbol(self, app_with_test_db):
        """Test search for single symbol in osakedata."""
        response = app_with_test_db.post('/search', data={
            'tickers': 'AAPL',
            'db_type': 'osakedata'
        })
        
        assert response.status_code == 200
        assert b'AAPL' in response.data
        assert b'table' in response.data
        
        # Check for OHLCV data columns
        soup = BeautifulSoup(response.data, 'html.parser')
        table = soup.find('table')
        assert table is not None
        
        # Should have osakedata columns
        headers = [th.get_text().strip() for th in table.find_all('th')]
        expected_columns = ['osake', 'pvm', 'open', 'high', 'low', 'close', 'volume']
        for col in expected_columns:
            assert any(col in header.lower() for header in headers)
    
    @pytest.mark.integration
    @pytest.mark.web
    def test_search_route_analysis_single_symbol(self, app_with_test_db):
        """Test search for single symbol in analysis database."""
        response = app_with_test_db.post('/search', data={
            'tickers': 'AAPL',
            'db_type': 'analysis'
        })
        
        assert response.status_code == 200
        assert b'AAPL' in response.data
        assert b'table' in response.data
        
        # Check for analysis data columns
        soup = BeautifulSoup(response.data, 'html.parser')
        table = soup.find('table')
        assert table is not None
        
        # Should have analysis columns
        headers = [th.get_text().strip() for th in table.find_all('th')]
        expected_columns = ['ticker', 'date', 'pattern']
        for col in expected_columns:
            assert any(col in header.lower() for header in headers)
    
    @pytest.mark.integration
    @pytest.mark.web
    def test_search_route_multiple_symbols(self, app_with_test_db):
        """Test search for multiple symbols."""
        response = app_with_test_db.post('/search', data={
            'tickers': 'AAPL, GOOGL, MSFT',
            'db_type': 'osakedata'
        })
        
        assert response.status_code == 200
        assert b'AAPL' in response.data
        assert b'GOOGL' in response.data
        assert b'MSFT' in response.data
        
        # Check record count
        soup = BeautifulSoup(response.data, 'html.parser')
        # Look for record count in the response
        assert b'table' in response.data
    
    @pytest.mark.integration
    @pytest.mark.web
    def test_search_route_partial_symbol(self, app_with_test_db):
        """Test partial symbol search."""
        response = app_with_test_db.post('/search', data={
            'tickers': 'A',
            'db_type': 'osakedata'
        })
        
        assert response.status_code == 200
        # Should find AAPL, AA, ABC
        assert b'AAPL' in response.data
        assert b'table' in response.data
    
    @pytest.mark.integration
    @pytest.mark.web
    def test_search_route_empty_input(self, app_with_test_db):
        """Test search with empty input."""
        response = app_with_test_db.post('/search', data={
            'tickers': '',
            'db_type': 'osakedata'
        })
        
        assert response.status_code == 200
        # Check for error message using BeautifulSoup to handle UTF-8 properly
        soup = BeautifulSoup(response.data, 'html.parser')
        error_div = soup.find('div', class_='error-box')
        assert error_div is not None
        assert 'Anna vähintään yksi hakutermi' in error_div.get_text()
    
    @pytest.mark.integration
    @pytest.mark.web
    def test_search_route_nonexistent_symbol(self, app_with_test_db):
        """Test search for nonexistent symbol."""
        response = app_with_test_db.post('/search', data={
            'tickers': 'NONEXISTENT',
            'db_type': 'osakedata'
        })
        
        assert response.status_code == 200
        # Check for error message using BeautifulSoup to handle UTF-8 properly
        soup = BeautifulSoup(response.data, 'html.parser')
        error_div = soup.find('div', class_='error-box')
        assert error_div is not None
        assert 'Ei löytynyt tietoja' in error_div.get_text()
    
    @pytest.mark.integration
    @pytest.mark.web
    def test_search_route_whitespace_handling(self, app_with_test_db):
        """Test search with extra whitespace."""
        response = app_with_test_db.post('/search', data={
            'tickers': '  AAPL  , GOOGL  ',
            'db_type': 'osakedata'
        })
        
        assert response.status_code == 200
        assert b'AAPL' in response.data
        assert b'GOOGL' in response.data
    
    @pytest.mark.integration
    @pytest.mark.web
    def test_search_route_case_insensitive(self, app_with_test_db):
        """Test case insensitive search."""
        response = app_with_test_db.post('/search', data={
            'tickers': 'aapl, googl',
            'db_type': 'osakedata'
        })
        
        assert response.status_code == 200
        assert b'AAPL' in response.data
        assert b'GOOGL' in response.data


class TestDeleteRoute:
    """Test suite for /delete route."""
    
    @pytest.mark.integration
    @pytest.mark.web
    def test_delete_route_success(self, app_with_test_db):
        """Test successful deletion."""
        # First verify data exists
        search_response = app_with_test_db.post('/search', data={
            'tickers': 'TEST',
            'db_type': 'osakedata'
        })
        assert b'TEST' in search_response.data
        
        # Delete the data
        response = app_with_test_db.post('/delete', data={
            'delete_tickers': 'TEST',
            'db_type': 'osakedata',
            'confirm_delete': 'kyllä'
        })
        
        assert response.status_code == 200
        assert b'Poistettu' in response.data
        
        # Check for success message
        soup = BeautifulSoup(response.data, 'html.parser')
        success_div = soup.find('div', class_='alert-success')
        assert success_div is not None
        
        # Verify data is gone
        search_after = app_with_test_db.post('/search', data={
            'tickers': 'TEST',
            'db_type': 'osakedata'
        })
        # Check for error message using BeautifulSoup
        soup = BeautifulSoup(search_after.data, 'html.parser')
        error_div = soup.find('div', class_='error-box')
        assert error_div is not None
        assert 'Ei löytynyt tietoja' in error_div.get_text()
    
    @pytest.mark.integration
    @pytest.mark.web
    def test_delete_route_empty_input(self, app_with_test_db):
        """Test delete with empty input."""
        response = app_with_test_db.post('/delete', data={
            'delete_tickers': '',
            'db_type': 'osakedata',
            'confirm_delete': 'kyllä'
        })
        
        assert response.status_code == 200
        assert b'Anna symbolit joiden data haluat poistaa' in response.data
        
        # Check error message
        soup = BeautifulSoup(response.data, 'html.parser')
        error_div = soup.find('div', class_='error-box')
        assert error_div is not None
    
    @pytest.mark.integration
    @pytest.mark.web
    def test_delete_route_no_confirmation(self, app_with_test_db):
        """Test delete without confirmation."""
        response = app_with_test_db.post('/delete', data={
            'delete_tickers': 'AAPL',
            'db_type': 'osakedata',
            'confirm_delete': 'ei'  # Wrong confirmation
        })
        
        assert response.status_code == 200
        assert b'Poistotoiminto peruutettu' in response.data
        
        # Check error message
        soup = BeautifulSoup(response.data, 'html.parser')
        error_div = soup.find('div', class_='error-box')
        assert error_div is not None
    
    @pytest.mark.integration
    @pytest.mark.web
    def test_delete_route_nonexistent_symbol(self, app_with_test_db):
        """Test delete of nonexistent symbol."""
        response = app_with_test_db.post('/delete', data={
            'delete_tickers': 'NONEXISTENT',
            'db_type': 'osakedata',
            'confirm_delete': 'kyllä'
        })
        
        assert response.status_code == 200
        # Check error message using BeautifulSoup
        soup = BeautifulSoup(response.data, 'html.parser')
        error_div = soup.find('div', class_='error-box')
        assert error_div is not None
        assert 'Ei löytynyt poistettavia rivejä' in error_div.get_text()
    
    @pytest.mark.integration
    @pytest.mark.web
    def test_delete_route_multiple_symbols(self, app_with_test_db):
        """Test delete multiple symbols."""
        response = app_with_test_db.post('/delete', data={
            'delete_tickers': 'AA, ABC',
            'db_type': 'osakedata',
            'confirm_delete': 'kyllä'
        })
        
        assert response.status_code == 200
        assert b'Poistettu' in response.data
        
        # Check success message
        soup = BeautifulSoup(response.data, 'html.parser')
        success_div = soup.find('div', class_='alert-success')
        assert success_div is not None
    
    @pytest.mark.integration
    @pytest.mark.web
    def test_delete_route_analysis_database(self, app_with_test_db):
        """Test delete from analysis database."""
        response = app_with_test_db.post('/delete', data={
            'delete_tickers': 'MULTI',
            'db_type': 'analysis',
            'confirm_delete': 'yes'  # English confirmation
        })
        
        assert response.status_code == 200
        # Should succeed and show success message


class TestAPIRoutes:
    """Test suite for API endpoints."""
    
    @pytest.mark.integration
    @pytest.mark.web
    def test_api_symbols_osakedata(self, app_with_test_db):
        """Test /api/symbols endpoint for osakedata."""
        response = app_with_test_db.get('/api/symbols?db_type=osakedata')
        
        assert response.status_code == 200
        assert response.content_type == 'application/json'
        
        symbols = json.loads(response.data)
        assert isinstance(symbols, list)
        assert 'AAPL' in symbols
        assert 'GOOGL' in symbols
        assert 'MSFT' in symbols
        
        # Should be sorted
        assert symbols == sorted(symbols)
    
    @pytest.mark.integration
    @pytest.mark.web
    def test_api_symbols_analysis(self, app_with_test_db):
        """Test /api/symbols endpoint for analysis."""
        response = app_with_test_db.get('/api/symbols?db_type=analysis')
        
        assert response.status_code == 200
        assert response.content_type == 'application/json'
        
        symbols = json.loads(response.data)
        assert isinstance(symbols, list)
        assert 'AAPL' in symbols
        assert 'GOOGL' in symbols
        assert 'MSFT' in symbols
    
    @pytest.mark.integration
    @pytest.mark.web
    def test_api_symbols_default_database(self, app_with_test_db):
        """Test /api/symbols endpoint with default database."""
        response = app_with_test_db.get('/api/symbols')
        
        assert response.status_code == 200
        assert response.content_type == 'application/json'
        
        symbols = json.loads(response.data)
        assert isinstance(symbols, list)
        # Should default to osakedata
        assert len(symbols) > 0
    
    @pytest.mark.integration
    @pytest.mark.web
    def test_api_symbols_invalid_database(self, app_with_test_db):
        """Test /api/symbols endpoint with invalid database type."""
        response = app_with_test_db.get('/api/symbols?db_type=invalid')
        
        assert response.status_code == 200
        assert response.content_type == 'application/json'
        
        symbols = json.loads(response.data)
        # Should default to osakedata and return symbols
        assert isinstance(symbols, list)


class TestFormValidation:
    """Test suite for form validation and edge cases."""
    
    @pytest.mark.integration
    @pytest.mark.web
    def test_search_with_only_commas(self, app_with_test_db):
        """Test search with only commas and spaces."""
        response = app_with_test_db.post('/search', data={
            'tickers': ', , , ,',
            'db_type': 'osakedata'
        })
        
        assert response.status_code == 200
        # Check error message using BeautifulSoup
        soup = BeautifulSoup(response.data, 'html.parser')
        error_div = soup.find('div', class_='error-box')
        assert error_div is not None
        assert 'Anna vähintään yksi kelvollinen hakutermi' in error_div.get_text()
    
    @pytest.mark.integration
    @pytest.mark.web
    def test_search_special_characters(self, app_with_test_db):
        """Test search with special characters."""
        response = app_with_test_db.post('/search', data={
            'tickers': 'XY-Z',
            'db_type': 'osakedata'
        })
        
        assert response.status_code == 200
        assert b'XY-Z' in response.data
    
    @pytest.mark.integration
    @pytest.mark.web
    def test_database_switching_persistence(self, app_with_test_db):
        """Test that database selection persists in form."""
        response = app_with_test_db.post('/search', data={
            'tickers': 'AAPL',
            'db_type': 'analysis'
        })
        
        assert response.status_code == 200
        # Check that the analysis database is still selected
        soup = BeautifulSoup(response.data, 'html.parser')
        db_selector = soup.find('select', {'id': 'db_type'})
        selected_option = db_selector.find('option', selected=True)
        assert selected_option['value'] == 'analysis'
    
    @pytest.mark.integration
    @pytest.mark.web
    def test_search_results_display_format(self, app_with_test_db):
        """Test that search results display correct format."""
        response = app_with_test_db.post('/search', data={
            'tickers': 'AAPL',
            'db_type': 'osakedata'
        })
        
        assert response.status_code == 200
        soup = BeautifulSoup(response.data, 'html.parser')
        
        # Check for search info
        info_boxes = soup.find_all('div', class_='info-box')
        assert len(info_boxes) > 0
        
        # Check table exists and has proper styling
        table = soup.find('table', {'id': 'stockTable'})
        assert table is not None
        assert 'table-striped' in table.get('class', [])
        assert 'table-hover' in table.get('class', [])
    
    @pytest.mark.integration
    @pytest.mark.web
    def test_symbol_badges_display(self, app_with_test_db):
        """Test that symbol badges are displayed correctly."""
        response = app_with_test_db.get('/')
        
        assert response.status_code == 200
        soup = BeautifulSoup(response.data, 'html.parser')
        
        # Check for symbol badges
        symbol_badges = soup.find_all('span', class_='symbol-badge')
        assert len(symbol_badges) > 0
        
        # Check that badges contain actual symbols
        symbols = [badge.get_text().strip() for badge in symbol_badges]
        assert 'AAPL' in symbols
        assert 'GOOGL' in symbols