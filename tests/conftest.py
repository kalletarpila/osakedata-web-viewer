import os
import sys
import pytest
import sqlite3
import tempfile
import shutil
from datetime import datetime, timedelta

# Add the parent directory to Python path to import main module
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from main import app, get_stock_data, get_available_symbols, delete_stock_data


class DatabaseFixtures:
    """Helper class to create test databases with sample data."""
    
    @staticmethod
    def create_osakedata_db(db_path):
        """Create test osakedata database with sample data."""
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Create table
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
        
        # Sample data with various test cases
        sample_data = [
            ('AAPL', '2024-01-15', 185.50, 187.25, 184.00, 186.75, 50000000),
            ('AAPL', '2024-01-16', 186.75, 188.50, 185.25, 187.90, 52000000),
            ('AAPL', '2024-01-17', 187.90, 189.00, 186.50, 188.25, 48000000),
            ('GOOGL', '2024-01-15', 142.30, 144.50, 141.80, 143.75, 25000000),
            ('GOOGL', '2024-01-16', 143.75, 145.20, 142.90, 144.60, 27000000),
            ('MSFT', '2024-01-15', 375.25, 378.90, 374.50, 377.80, 30000000),
            ('MSFT', '2024-01-16', 377.80, 380.25, 376.00, 379.50, 32000000),
            ('AA', '2024-01-15', 45.20, 46.80, 44.75, 46.25, 5000000),  # Matches "AA" prefix
            ('ABC', '2024-01-15', 12.50, 13.25, 12.00, 12.90, 2000000),  # Matches "A" prefix
            ('TEST', '2024-01-15', 100.00, 101.00, 99.00, 100.50, 1000000),
            # Special characters test
            ('XY-Z', '2024-01-15', 50.00, 51.00, 49.50, 50.75, 1500000),
            # Duplicate entries for testing
            ('DUP', '2024-01-15', 20.00, 21.00, 19.50, 20.50, 1000000),
            ('DUP', '2024-01-15', 20.00, 21.00, 19.50, 20.50, 1000000),
        ]
        
        cursor.executemany('''
            INSERT INTO osakedata (osake, pvm, open, high, low, close, volume)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', sample_data)
        
        conn.commit()
        conn.close()
    
    @staticmethod
    def create_analysis_db(db_path):
        """Create test analysis database with sample data."""
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Create table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS analysis_findings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ticker TEXT,
                date TEXT,
                pattern TEXT,
                UNIQUE(ticker, date, pattern)
            )
        ''')
        
        # Sample analysis data
        sample_data = [
            ('AAPL', '2024-01-15', 'Hammer'),
            ('AAPL', '2024-01-16', 'Bullish Engulfing'),
            ('AAPL', '2024-01-17', 'Dragonfly Doji'),
            ('GOOGL', '2024-01-15', 'Piercing Pattern'),
            ('GOOGL', '2024-01-16', 'Morning Star'),
            ('MSFT', '2024-01-15', 'Hammer'),
            ('MSFT', '2024-01-16', 'Three White Soldiers'),
            ('AA', '2024-01-15', 'Doji'),  # Matches "AA" prefix
            ('ABC', '2024-01-15', 'Spinning Top'),  # Matches "A" prefix
            ('TEST', '2024-01-15', 'Hammer'),
            # Multiple patterns for same ticker/date
            ('MULTI', '2024-01-15', 'Hammer'),
            ('MULTI', '2024-01-15', 'Doji'),
            ('MULTI', '2024-01-16', 'Bullish Engulfing'),
        ]
        
        cursor.executemany('''
            INSERT OR IGNORE INTO analysis_findings (ticker, date, pattern)
            VALUES (?, ?, ?)
        ''', sample_data)
        
        conn.commit()
        conn.close()
    
    @staticmethod
    def create_empty_db(db_path, db_type='osakedata'):
        """Create empty test database."""
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        if db_type == 'osakedata':
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
        else:
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS analysis_findings (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    ticker TEXT,
                    date TEXT,
                    pattern TEXT,
                    UNIQUE(ticker, date, pattern)
                )
            ''')
        
        conn.commit()
        conn.close()


@pytest.fixture(scope='session')
def temp_test_dir():
    """Create temporary directory for test databases."""
    temp_dir = tempfile.mkdtemp(prefix='test_stock_viewer_')
    yield temp_dir
    shutil.rmtree(temp_dir, ignore_errors=True)


@pytest.fixture
def test_osakedata_db(temp_test_dir):
    """Create temporary osakedata test database."""
    db_path = os.path.join(temp_test_dir, 'test_osakedata.db')
    DatabaseFixtures.create_osakedata_db(db_path)
    return db_path


@pytest.fixture
def test_analysis_db(temp_test_dir):
    """Create temporary analysis test database."""
    db_path = os.path.join(temp_test_dir, 'test_analysis.db')
    DatabaseFixtures.create_analysis_db(db_path)
    return db_path


@pytest.fixture
def empty_osakedata_db(temp_test_dir):
    """Create empty osakedata test database."""
    db_path = os.path.join(temp_test_dir, 'empty_osakedata.db')
    DatabaseFixtures.create_empty_db(db_path, 'osakedata')
    return db_path


@pytest.fixture
def empty_analysis_db(temp_test_dir):
    """Create empty analysis test database."""
    db_path = os.path.join(temp_test_dir, 'empty_analysis.db')
    DatabaseFixtures.create_empty_db(db_path, 'analysis')
    return db_path


@pytest.fixture
def corrupted_db(temp_test_dir):
    """Create corrupted database file."""
    db_path = os.path.join(temp_test_dir, 'corrupted.db')
    with open(db_path, 'w') as f:
        f.write('This is not a valid SQLite database file!')
    return db_path


@pytest.fixture
def app_with_test_db(test_osakedata_db, test_analysis_db, monkeypatch):
    """Flask app configured to use test databases."""
    test_db_paths = {
        'osakedata': test_osakedata_db,
        'analysis': test_analysis_db
    }
    
    # Import main module and monkeypatch DB_PATHS
    import main
    monkeypatch.setattr(main, 'DB_PATHS', test_db_paths)
    
    main.app.config['TESTING'] = True
    main.app.config['WTF_CSRF_ENABLED'] = False
    
    with main.app.test_client() as client:
        with main.app.app_context():
            yield client


@pytest.fixture
def sample_search_terms():
    """Sample search terms for testing."""
    return {
        'single': ['AAPL'],
        'multiple': ['AAPL', 'GOOGL'],
        'partial': ['A'],  # Should match AAPL, AA, ABC
        'mixed': ['AAPL', 'GOO'],  # Exact and partial
        'nonexistent': ['NONEXISTENT'],
        'empty': [],
        'special_chars': ['XY-Z'],
        'case_insensitive': ['aapl', 'googl']
    }