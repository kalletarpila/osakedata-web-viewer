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
import os
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


class TestLargeDatasetUI:
    """Testit käyttöliittymän toiminnallisuudelle suurten tietomäärien kanssa - pagination ja suorituskyky"""

    @pytest.fixture
    def large_symbols_db(self, temp_test_dir, monkeypatch):
        """Luo tietokanta jossa on paljon symboleja (>100) pagination-testausta varten"""
        import main
        
        # Luo väliaikaiset tietokantatiedostot
        osakedata_path = os.path.join(temp_test_dir, 'large_symbols_osakedata.db')
        analysis_path = os.path.join(temp_test_dir, 'large_symbols_analysis.db')
        
        # Luo tietokannat jossa on yli 200 symbolia
        self._create_large_symbols_db(osakedata_path, analysis_path)
        
        # Käytä väliaikaisia tietokantoja
        monkeypatch.setattr(main, 'DB_PATHS', {'osakedata': osakedata_path, 'analysis': analysis_path})
        
        with main.app.test_client() as client:
            yield client
    
    def _create_large_symbols_db(self, osakedata_path, analysis_path):
        """Luo tietokannat joissa on 200+ symbolia pagination-testausta varten"""
        import sqlite3
        from datetime import datetime, timedelta
        import random
        import string
        
        # Osakedata tietokanta
        with sqlite3.connect(osakedata_path) as conn:
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
            
            # Luo 250 eri symbolia (A001-Z250 tyyliin)
            base_date = datetime(2024, 1, 1)
            symbols = []
            
            # Luo symboleja A001-A099, B001-B099, C001-C052 = 250kpl 
            for letter in string.ascii_uppercase[:3]:  # A, B, C
                limit = 52 if letter == 'C' else 99
                for i in range(1, limit + 1):
                    symbol = f'{letter}{i:03d}'
                    symbols.append(symbol)
            
            for symbol in symbols:
                # Jokaiselle symbolille 5 päivän data
                for day in range(5):
                    date = base_date + timedelta(days=day)
                    base_price = random.uniform(10, 500)
                    
                    open_price = base_price * random.uniform(0.98, 1.02)
                    high_price = open_price * random.uniform(1.001, 1.05)
                    low_price = open_price * random.uniform(0.95, 0.999)
                    close_price = random.uniform(low_price, high_price)
                    volume = random.randint(10000, 1000000)
                    
                    cursor.execute('''
                        INSERT INTO osakedata (osake, pvm, open, high, low, close, volume)
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                    ''', (symbol, date.strftime('%Y-%m-%d'), open_price, high_price, low_price, close_price, volume))
        
        # Analysis tietokanta
        with sqlite3.connect(analysis_path) as conn:
            cursor = conn.cursor()
            
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS analysis_findings (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    ticker TEXT,
                    date TEXT,
                    pattern TEXT
                )
            ''')
            
            # Sama 250 symbolia analysis tietokantaan
            analysis_types = ['Hammer', 'Doji', 'Engulfing', 'Shooting Star', 'Morning Star']
            
            for symbol in symbols:
                # Jokaiselle symbolille 2 analyysiä
                for i in range(2):
                    date = base_date + timedelta(days=i)
                    pattern = random.choice(analysis_types)
                    
                    cursor.execute('''
                        INSERT INTO analysis_findings (ticker, date, pattern)
                        VALUES (?, ?, ?)
                    ''', (symbol, date.strftime('%Y-%m-%d'), pattern))

    @pytest.mark.integration
    @pytest.mark.web
    def test_pagination_ui_elements_present(self, large_symbols_db):
        """Testaa että pagination UI-elementit ovat läsnä kun symboleja on paljon"""
        response = large_symbols_db.get('/')
        assert response.status_code == 200
        
        # Tarkista että pagination HTML-elementit löytyvät
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(response.data, 'html.parser')
        
        # Pagination kontti
        pagination_div = soup.find('div', {'id': 'symbol-pagination'})
        assert pagination_div is not None, "Pagination div puuttuu"
        
        # Pagination navigation
        pagination_nav = soup.find('nav')
        assert pagination_nav is not None, "Pagination navigation puuttuu"

    @pytest.mark.integration
    @pytest.mark.web
    def test_large_symbols_api_performance(self, large_symbols_db):
        """Testaa että /api/symbols toimii nopeasti suurellakin symbolimäärällä"""
        import time
        
        start_time = time.time()
        response = large_symbols_db.get('/api/symbols?db_type=osakedata')
        end_time = time.time()
        
        elapsed_time = end_time - start_time
        
        assert response.status_code == 200
        symbols = response.get_json()
        assert len(symbols) == 250, f"Pitäisi olla 250 symbolia, oli {len(symbols)}"
        assert elapsed_time < 2.0, f"API-kutsu kesti liian kauan: {elapsed_time:.2f} sekuntia"

    @pytest.mark.integration 
    @pytest.mark.web
    def test_symbols_pagination_javascript_constants(self, large_symbols_db):
        """Testaa että JavaScript pagination-vakiot ovat oikein"""
        response = large_symbols_db.get('/')
        assert response.status_code == 200
        
        response_text = response.get_data(as_text=True)
        
        # Tarkista että symbolsPerPage on määritelty
        assert 'symbolsPerPage = 100' in response_text, "symbolsPerPage vakio puuttuu tai on väärä"
        
        # Tarkista että pagination funktiot löytyvät
        assert 'function renderPagination()' in response_text, "renderPagination funktio puuttuu"
        assert 'function changePage(' in response_text, "changePage funktio puuttuu"

    @pytest.mark.integration
    @pytest.mark.web 
    def test_symbols_display_with_large_dataset(self, large_symbols_db):
        """Testaa että symbolien näyttäminen toimii suurella datamäärällä"""
        response = large_symbols_db.get('/')
        assert response.status_code == 200
        
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(response.data, 'html.parser')
        
        # Tarkista että symbol-container löytyy
        symbols_container = soup.find('div', {'id': 'symbol-container'})
        assert symbols_container is not None, "Symbol container puuttuu"
        
        # Tarkista että JavaScript lataa symbolit
        response_text = response.get_data(as_text=True)
        assert 'loadSymbols()' in response_text or 'loadAvailableSymbols' in response_text, "Symbol loading JavaScript puuttuu"

    @pytest.mark.integration
    @pytest.mark.web
    def test_search_functionality_with_large_dataset(self, large_symbols_db):
        """Testaa hakutoiminnallisuus suurella symbolimäärällä"""
        response = large_symbols_db.get('/')
        assert response.status_code == 200
        
        response_text = response.get_data(as_text=True)
        
        # Tarkista että haku-JavaScript löytyy
        assert 'searchSymbols' in response_text or 'filterSymbols' in response_text, "Haku JavaScript puuttuu"
        
        # Tarkista että hakukenttä löytyy
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(response.data, 'html.parser')
        
        search_input = soup.find('input', {'id': 'symbol-search'})
        assert search_input is not None, "Symbol search input puuttuu"

    @pytest.mark.integration
    @pytest.mark.web
    def test_responsive_design_elements(self, large_symbols_db):
        """Testaa että responsiiviset design-elementit löytyvät suurelle datamäärälle"""
        response = large_symbols_db.get('/')
        assert response.status_code == 200
        
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(response.data, 'html.parser')
        
        # Tarkista Bootstrap responsive classit
        containers = soup.find_all(class_=lambda x: x and 'col-' in x)
        assert len(containers) > 0, "Bootstrap responsive column classit puuttuvat"
        
        # Tarkista että meta viewport tag löytyy
        viewport_meta = soup.find('meta', {'name': 'viewport'})
        assert viewport_meta is not None, "Viewport meta tag puuttuu responsiivisuudelle"


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
        """Test that symbol display infrastructure is present (symbols loaded via JS)."""
        response = app_with_test_db.get('/')
        
        assert response.status_code == 200
        soup = BeautifulSoup(response.data, 'html.parser')
        
        # Check that the symbol container exists for JS to populate
        symbol_container = soup.find('div', id='symbol-container')
        assert symbol_container is not None
        
        # Check that the symbols API endpoint works
        api_response = app_with_test_db.get('/api/symbols?db_type=osakedata')
        assert api_response.status_code == 200
        
        # Check that API returns test symbols
        api_data = api_response.get_json()
        # API returns list when no pagination is used
        symbols = api_data if isinstance(api_data, list) else api_data.get('symbols', [])
        assert 'AAPL' in symbols
        assert 'GOOGL' in symbols


class TestClearDatabase:
    """Testit tietokannan tyhjentämiselle - VAARALLINEN TOIMINTO"""

    @pytest.mark.integration  
    @pytest.mark.web
    def test_clear_database_missing_confirmation(self, app_with_test_db):
        """Testi että clear database vaatii vahvistuksen"""
        response = app_with_test_db.post('/clear_database', data={
            'db_type': 'osakedata'
            # Ei confirm_clear tai double_confirm
        })
        assert response.status_code == 200
        assert 'Tietokannan tyhjentäminen vaatii vahvistuksen' in response.get_data(as_text=True)

    @pytest.mark.integration
    @pytest.mark.web  
    def test_clear_database_missing_double_confirmation(self, app_with_test_db):
        """Testi että clear database vaatii tuplan vahvistuksen"""
        response = app_with_test_db.post('/clear_database', data={
            'db_type': 'osakedata',
            'confirm_clear': 'kyllä'
            # Ei double_confirm
        })
        assert response.status_code == 200
        assert 'TYHJENNÄ' in response.get_data(as_text=True)

    @pytest.mark.integration
    @pytest.mark.web
    def test_clear_database_wrong_double_confirmation(self, app_with_test_db):
        """Testi että clear database vaatii oikean tuplan vahvistuksen"""
        response = app_with_test_db.post('/clear_database', data={
            'db_type': 'osakedata', 
            'confirm_clear': 'kyllä',
            'double_confirm': 'VÄÄRÄ'
        })
        assert response.status_code == 200
        assert 'TYHJENNÄ' in response.get_data(as_text=True)

    @pytest.mark.integration
    @pytest.mark.web
    def test_clear_database_success_osakedata(self, app_with_test_db):
        """Testi että osakedata tietokannan tyhjentäminen toimii"""
        # Tyhjennä tietokanta
        response = app_with_test_db.post('/clear_database', data={
            'db_type': 'osakedata',
            'confirm_clear': 'kyllä', 
            'double_confirm': 'TYHJENNÄ'
        })
        assert response.status_code == 200
        response_text = response.get_data(as_text=True)
        # Etsi success viestiä HTML:stä
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(response_text, 'html.parser')
        success_div = soup.find('div', class_='alert-success')
        assert success_div is not None, "Success viesti puuttui"
        assert 'osakedata tyhjennetty' in success_div.get_text() or 'Tietokanta osakedata tyhjennetty' in success_div.get_text()

    @pytest.mark.integration
    @pytest.mark.web  
    def test_clear_database_success_analysis(self, app_with_test_db):
        """Testi että analysis tietokannan tyhjentäminen toimii"""
        # Tyhjennä tietokanta
        response = app_with_test_db.post('/clear_database', data={
            'db_type': 'analysis',
            'confirm_clear': 'kylla',
            'double_confirm': 'TYHJENNÄ'
        })
        assert response.status_code == 200
        response_text = response.get_data(as_text=True)
        # Etsi success viestiä HTML:stä
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(response_text, 'html.parser')
        success_div = soup.find('div', class_='alert-success')
        assert success_div is not None, "Success viesti puuttui"
        assert 'analysis tyhjennetty' in success_div.get_text() or 'Tietokanta analysis tyhjennetty' in success_div.get_text()

    @pytest.mark.integration
    @pytest.mark.web
    def test_clear_database_empty_database(self, app_with_test_db):
        """Testi että tyhjän tietokannan tyhjentäminen toimii"""
        # Tyhjennä ensin tietokanta
        app_with_test_db.post('/clear_database', data={
            'db_type': 'osakedata',
            'confirm_clear': 'yes',
            'double_confirm': 'TYHJENNÄ'  
        })
        
        # Yritä tyhjentää uudestaan
        response = app_with_test_db.post('/clear_database', data={
            'db_type': 'osakedata',
            'confirm_clear': 'kyllä',
            'double_confirm': 'TYHJENNÄ'
        })
        assert response.status_code == 200
        response_text = response.get_data(as_text=True)
        assert 'oli jo tyhjä' in response_text

    @pytest.mark.integration  
    @pytest.mark.web
    def test_clear_database_various_confirmations(self, app_with_test_db):
        """Testi että eri vahvistusmuodot hyväksytään"""
        # Testaa 'yes' vahvistus
        response = app_with_test_db.post('/clear_database', data={
            'db_type': 'osakedata',
            'confirm_clear': 'yes',
            'double_confirm': 'TYHJENNÄ'
        })
        assert response.status_code == 200
        
        # Testaa 'kylla' vahvistus  
        response = app_with_test_db.post('/clear_database', data={
            'db_type': 'osakedata',
            'confirm_clear': 'kylla',
            'double_confirm': 'TYHJENNÄ'
        })
        assert response.status_code == 200


class TestClearDatabaseLargeDataset:
    """Testit tietokannan tyhjentämiselle suurella datamäärällä"""

    @pytest.fixture
    def large_test_db(self, temp_test_dir, monkeypatch):
        """Luo testitietokanta suurella datamäärällä"""
        import main
        import os
        
        # Luo testitietokannat suurella datamäärällä
        osakedata_path = os.path.join(temp_test_dir, 'large_osakedata.db')
        analysis_path = os.path.join(temp_test_dir, 'large_analysis.db')
        
        # Luo osakedata tietokanta 1000 rivill÷
        self._create_large_osakedata_db(osakedata_path)
        
        # Luo analysis tietokanta 500 rivillä
        self._create_large_analysis_db(analysis_path)
        
        # Patch tietokantapolut
        test_db_paths = {
            'osakedata': osakedata_path,
            'analysis': analysis_path
        }
        
        monkeypatch.setattr(main, 'DB_PATHS', test_db_paths)
        
        main.app.config['TESTING'] = True
        main.app.config['WTF_CSRF_ENABLED'] = False
        
        with main.app.test_client() as client:
            with main.app.app_context():
                yield client

    def _create_large_osakedata_db(self, db_path):
        """Luo osakedata tietokanta 1000 rivillä (100 osaketta × 10 päivää)"""
        import sqlite3
        import random
        from datetime import datetime, timedelta
        
        with sqlite3.connect(db_path) as conn:
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
            
            # Luo 100 osaketta, kullekin 10 päivän data = 1000 riviä
            base_date = datetime(2024, 1, 1)
            
            for i in range(100):
                symbol = f'STOCK{i:03d}'  # STOCK001, STOCK002, ...
                base_price = random.uniform(50, 200)
                
                for day in range(10):
                    date = base_date + timedelta(days=day)
                    
                    # Simuloi päivän hinnanmuutoksia
                    daily_change = random.uniform(-0.05, 0.05)
                    open_price = base_price * (1 + daily_change)
                    
                    high_price = open_price * random.uniform(1.001, 1.03)
                    low_price = open_price * random.uniform(0.97, 0.999)
                    close_price = random.uniform(low_price, high_price)
                    volume = random.randint(100000, 5000000)
                    
                    cursor.execute('''
                        INSERT INTO osakedata (osake, pvm, open, high, low, close, volume)
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                    ''', (symbol, date.strftime('%Y-%m-%d'), open_price, high_price, low_price, close_price, volume))
                    
                    base_price = close_price

    def _create_large_analysis_db(self, db_path):
        """Luo analysis tietokanta 500 rivillä (100 osaketta × 5 patternia)"""
        import sqlite3
        import random
        from datetime import datetime, timedelta
        
        with sqlite3.connect(db_path) as conn:
            cursor = conn.cursor()
            
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS analysis_findings (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    ticker TEXT,
                    date TEXT,
                    pattern TEXT
                )
            ''')
            
            # Luo 100 osaketta, kullekin 5 patternia = 500 riviä
            base_date = datetime(2024, 1, 15)
            analysis_types = ['Hammer', 'Doji', 'Engulfing', 'Shooting Star', 'Morning Star']
            
            for i in range(100):
                symbol = f'STOCK{i:03d}'  # Samat symbolit kuin osakedata:ssa
                
                for j, analysis_type in enumerate(analysis_types):
                    date = base_date + timedelta(days=j)
                    
                    cursor.execute('''
                        INSERT INTO analysis_findings (ticker, date, pattern)
                        VALUES (?, ?, ?)
                    ''', (symbol, date.strftime('%Y-%m-%d'), analysis_type))

    @pytest.mark.integration
    @pytest.mark.web
    def test_clear_large_osakedata_database(self, large_test_db):
        """Testi suureen osakedata tietokannan (1000 riviä) tyhjentämiselle"""
        # Varmista että tietokannassa on dataa
        response = large_test_db.get('/api/symbols?db_type=osakedata')
        symbols = response.get_json()
        assert len(symbols) == 100, f"Pitäisi olla 100 symbolia, oli {len(symbols)}"
        
        # Tyhjennä tietokanta
        response = large_test_db.post('/clear_database', data={
            'db_type': 'osakedata',
            'confirm_clear': 'kyllä',
            'double_confirm': 'TYHJENNÄ'
        })
        
        assert response.status_code == 200
        response_text = response.get_data(as_text=True)
        
        # Varmista että success viesti näkyy
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(response_text, 'html.parser')
        success_div = soup.find('div', class_='alert-success')
        assert success_div is not None, "Success viesti puuttui"
        success_text = success_div.get_text()
        
        # Tarkista että rivienmäärä mainitaan
        assert '1000' in success_text, f"1000 riviä ei mainittu success viestissä: {success_text}"
        
        # Varmista että tietokanta on tyhjä
        response = large_test_db.get('/api/symbols?db_type=osakedata')
        symbols_after = response.get_json()
        assert len(symbols_after) == 0, f"Tietokannan pitäisi olla tyhjä tyhjennyksen jälkeen, mutta siellä on {len(symbols_after)} symbolia"

    @pytest.mark.integration
    @pytest.mark.web
    def test_clear_large_analysis_database(self, large_test_db):
        """Testi suureen analysis tietokannan (500 riviä) tyhjentämiselle"""
        # Varmista että tietokannassa on dataa
        response = large_test_db.get('/api/symbols?db_type=analysis')
        symbols = response.get_json()
        assert len(symbols) == 100, f"Pitäisi olla 100 symbolia, oli {len(symbols)}"
        
        # Tyhjennä tietokanta
        response = large_test_db.post('/clear_database', data={
            'db_type': 'analysis',
            'confirm_clear': 'yes',
            'double_confirm': 'TYHJENNÄ'
        })
        
        assert response.status_code == 200
        response_text = response.get_data(as_text=True)
        
        # Varmista että success viesti näkyy
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(response_text, 'html.parser')
        success_div = soup.find('div', class_='alert-success')
        assert success_div is not None, "Success viesti puuttui"
        success_text = success_div.get_text()
        
        # Tarkista että rivienmäärä mainitaan (noin 500)
        import re
        row_count_match = re.search(r'(\d+) riviä', success_text)
        assert row_count_match, f"Rivimäärää ei mainittu success viestissä: {success_text}"
        actual_rows = int(row_count_match.group(1))
        assert actual_rows >= 400 and actual_rows <= 1100, f"Odotettiin 400-1100 riviä, sain {actual_rows}: {success_text}"
        
        # Varmista että tietokanta on tyhjä
        response = large_test_db.get('/api/symbols?db_type=analysis')
        symbols_after = response.get_json()
        assert len(symbols_after) == 0, f"Analysis tietokannan pitäisi olla tyhjä tyhjennyksen jälkeen"

    @pytest.mark.integration
    @pytest.mark.web
    def test_clear_database_performance_timing(self, large_test_db):
        """Testi että suurenkin tietokannan tyhjentäminen on nopeaa (< 5 sekuntia)"""
        import time
        
        start_time = time.time()
        
        response = large_test_db.post('/clear_database', data={
            'db_type': 'osakedata',
            'confirm_clear': 'kyllä',
            'double_confirm': 'TYHJENNÄ'
        })
        
        end_time = time.time()
        elapsed_time = end_time - start_time
        
        assert response.status_code == 200
        assert elapsed_time < 5.0, f"Tietokannan tyhjentäminen kesti liian kauan: {elapsed_time:.2f} sekuntia"

    @pytest.mark.integration
    @pytest.mark.web 
    def test_clear_database_concurrent_operations(self, large_test_db):
        """Testi että tietokannan tyhjentäminen toimii vaikka muita operaatioita tehdään samanaikaisesti"""
        # Hae symbolit ensin
        response1 = large_test_db.get('/api/symbols?db_type=osakedata')
        assert response1.status_code == 200
        
        # Tyhjennä tietokanta
        response2 = large_test_db.post('/clear_database', data={
            'db_type': 'osakedata',
            'confirm_clear': 'kyllä',
            'double_confirm': 'TYHJENNÄ'
        })
        assert response2.status_code == 200
        
        # Yritä hakea symbolit uudestaan - pitäisi olla tyhjä
        response3 = large_test_db.get('/api/symbols?db_type=osakedata')
        assert response3.status_code == 200
        symbols = response3.get_json()
        assert len(symbols) == 0

    @pytest.mark.integration
    @pytest.mark.web
    def test_clear_database_invalid_db_type(self, large_test_db):
        """Testi että virheellinen tietokantatyyppi käsitellään oikein"""
        response = large_test_db.post('/clear_database', data={
            'db_type': 'invalid_db_type',
            'confirm_clear': 'kyllä',
            'double_confirm': 'TYHJENNÄ'
        })
        
        assert response.status_code == 200
        response_text = response.get_data(as_text=True)
        assert 'Virhe' in response_text or 'Error' in response_text

    @pytest.mark.integration
    @pytest.mark.web
    def test_clear_database_sql_injection_protection(self, large_test_db):
        """Testi että SQL-injektiot eivät onnistu tietokannan tyhjentämisessä"""
        # Yritä SQL-injektiota db_type parametrissa
        malicious_inputs = [
            "osakedata'; DROP TABLE osakedata; --",
            "osakedata UNION SELECT * FROM sqlite_master",
            "osakedata; DELETE FROM analysis_findings; --"
        ]
        
        for malicious_input in malicious_inputs:
            response = large_test_db.post('/clear_database', data={
                'db_type': malicious_input,
                'confirm_clear': 'kyllä',
                'double_confirm': 'TYHJENNÄ'
            })
            
            # Ei pitäisi kaataa sovellusta
            assert response.status_code == 200
            
        # Varmista että tietokannat ovat vielä olemassa ja toimivat
        response = large_test_db.get('/api/symbols?db_type=osakedata')
        assert response.status_code == 200