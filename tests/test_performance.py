"""
Performance and stress tests for the stock data viewer application.

Tests cover:
- Response times under various loads
- Memory usage patterns
- Database query performance
- Large dataset handling
- Concurrent user simulation
- Resource cleanup verification
"""

import pytest
import time
import threading
import os
import sqlite3
import psutil
from concurrent.futures import ThreadPoolExecutor, as_completed

from main import get_stock_data, get_available_symbols, delete_stock_data


class TestPerformance:
    """Test suite for performance benchmarks."""
    
    @pytest.mark.slow
    @pytest.mark.db
    def test_search_performance_single_symbol(self, monkeypatch, test_osakedata_db):
        """Test search performance for single symbol lookup."""
        monkeypatch.setattr('main.DB_PATHS', {'osakedata': test_osakedata_db})
        
        # Warm up
        get_stock_data(['AAPL'], 'osakedata')
        
        # Measure performance
        start_time = time.time()
        iterations = 100
        
        for _ in range(iterations):
            df, error, found_symbols = get_stock_data(['AAPL'], 'osakedata')
            assert error is None
            assert not df.empty
        
        end_time = time.time()
        avg_time = (end_time - start_time) / iterations
        
        # Should be fast (less than 10ms per query on average)
        assert avg_time < 0.01, f"Average query time too slow: {avg_time:.4f}s"
    
    @pytest.mark.slow
    @pytest.mark.db
    def test_search_performance_multiple_symbols(self, monkeypatch, test_osakedata_db):
        """Test search performance for multiple symbol lookup."""
        monkeypatch.setattr('main.DB_PATHS', {'osakedata': test_osakedata_db})
        
        symbols = ['AAPL', 'GOOGL', 'MSFT', 'AA', 'ABC']
        
        start_time = time.time()
        iterations = 50
        
        for _ in range(iterations):
            df, error, found_symbols = get_stock_data(symbols, 'osakedata')
            assert error is None
            assert not df.empty
        
        end_time = time.time()
        avg_time = (end_time - start_time) / iterations
        
        # Should handle multiple symbols efficiently (less than 20ms)
        assert avg_time < 0.02, f"Multiple symbol query too slow: {avg_time:.4f}s"
    
    @pytest.mark.slow
    @pytest.mark.db
    def test_symbols_list_performance(self, monkeypatch, test_osakedata_db):
        """Test performance of getting available symbols."""
        monkeypatch.setattr('main.DB_PATHS', {'osakedata': test_osakedata_db})
        
        start_time = time.time()
        iterations = 100
        
        for _ in range(iterations):
            symbols = get_available_symbols('osakedata')
            assert len(symbols) > 0
        
        end_time = time.time()
        avg_time = (end_time - start_time) / iterations
        
        # Should be very fast (less than 5ms)
        assert avg_time < 0.005, f"Symbol listing too slow: {avg_time:.4f}s"


class TestScalability:
    """Test suite for scalability and large dataset handling."""
    
    @pytest.mark.slow
    @pytest.mark.db
    def test_large_dataset_creation_and_query(self, monkeypatch, temp_test_dir):
        """Test performance with large datasets."""
        # Create large test database
        large_db = os.path.join(temp_test_dir, 'large_perf_test.db')
        conn = sqlite3.connect(large_db)
        cursor = conn.cursor()
        
        cursor.execute('''
            CREATE TABLE osakedata (
                id INTEGER PRIMARY KEY,
                osake TEXT,
                pvm TEXT,
                open REAL,
                high REAL,
                low REAL,
                close REAL,
                volume INTEGER
            )
        ''')
        
        # Insert large dataset (10,000 records across 100 symbols)
        print("\\nCreating large test dataset...")
        large_data = []
        for symbol_idx in range(100):
            symbol = f'STOCK{symbol_idx:03d}'
            for day in range(100):  # 100 days per symbol
                large_data.append((
                    symbol, f'2024-{(day % 12) + 1:02d}-{(day % 28) + 1:02d}',
                    100.0 + symbol_idx, 101.0 + symbol_idx,
                    99.0 + symbol_idx, 100.5 + symbol_idx, 1000000 + day
                ))
        
        # Insert in batches for better performance
        batch_size = 1000
        for i in range(0, len(large_data), batch_size):
            batch = large_data[i:i + batch_size]
            cursor.executemany('''
                INSERT INTO osakedata (osake, pvm, open, high, low, close, volume)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', batch)
        
        conn.commit()
        conn.close()
        
        monkeypatch.setattr('main.DB_PATHS', {'osakedata': large_db})
        
        print(f"Testing queries on {len(large_data)} records...")
        
        # Test single symbol query performance
        start_time = time.time()
        df, error, found_symbols = get_stock_data(['STOCK001'], 'osakedata')
        single_query_time = time.time() - start_time
        
        assert error is None
        assert len(df) == 100  # 100 records for STOCK001
        assert single_query_time < 0.1, f"Large dataset single query too slow: {single_query_time:.4f}s"
        
        # Test partial match query (more expensive)
        start_time = time.time()
        df, error, found_symbols = get_stock_data(['STOCK001', 'STOCK002', 'STOCK003'], 'osakedata')  # Multiple exact matches
        partial_query_time = time.time() - start_time
        
        assert error is None
        assert len(df) == 300  # 3 symbols × 100 records each
        assert partial_query_time < 0.5, f"Large dataset partial query too slow: {partial_query_time:.4f}s"
        
        # Test getting all symbols
        start_time = time.time()
        symbols = get_available_symbols('osakedata')
        symbols_query_time = time.time() - start_time
        
        assert len(symbols) == 100
        assert symbols_query_time < 0.1, f"Large dataset symbols query too slow: {symbols_query_time:.4f}s"
    
    @pytest.mark.slow
    @pytest.mark.db
    def test_memory_usage_monitoring(self, monkeypatch, temp_test_dir):
        """Test memory usage during large operations."""
        # Create moderate-sized dataset
        memory_db = os.path.join(temp_test_dir, 'memory_test.db')
        conn = sqlite3.connect(memory_db)
        cursor = conn.cursor()
        
        cursor.execute('''
            CREATE TABLE osakedata (
                id INTEGER PRIMARY KEY,
                osake TEXT,
                pvm TEXT,
                open REAL,
                high REAL,
                low REAL,
                close REAL,
                volume INTEGER
            )
        ''')
        
        # Insert 5000 records
        data = []
        for i in range(5000):
            data.append((
                f'SYM{i % 50:03d}', f'2024-01-{(i % 28) + 1:02d}',
                100.0 + (i % 100), 101.0 + (i % 100),
                99.0 + (i % 100), 100.5 + (i % 100), 1000000 + i
            ))
        
        cursor.executemany('''
            INSERT INTO osakedata (osake, pvm, open, high, low, close, volume)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', data)
        
        conn.commit()
        conn.close()
        
        monkeypatch.setattr('main.DB_PATHS', {'osakedata': memory_db})
        
        # Get initial memory usage
        process = psutil.Process()
        initial_memory = process.memory_info().rss / 1024 / 1024  # MB
        
        # Perform memory-intensive operation
        df, error, found_symbols = get_stock_data(['SYM'], 'osakedata')  # Should match many records
        
        # Get memory after operation
        after_memory = process.memory_info().rss / 1024 / 1024  # MB
        memory_increase = after_memory - initial_memory
        
        assert error is None
        assert not df.empty
        
        # Memory increase should be reasonable (less than 100MB for this test)
        assert memory_increase < 100, f"Memory usage too high: {memory_increase:.2f}MB increase"


class TestConcurrentLoad:
    """Test suite for concurrent load and stress testing."""
    
    @pytest.mark.slow
    @pytest.mark.db
    def test_concurrent_queries_stress(self, monkeypatch, test_osakedata_db):
        """Test handling of many concurrent queries."""
        monkeypatch.setattr('main.DB_PATHS', {'osakedata': test_osakedata_db})
        
        def worker_query(worker_id):
            """Worker function for concurrent testing."""
            results = []
            symbols = ['AAPL', 'GOOGL', 'MSFT', 'AA', 'ABC']
            
            for i in range(10):  # 10 queries per worker
                symbol = symbols[i % len(symbols)]
                start_time = time.time()
                df, error, found_symbols = get_stock_data([symbol], 'osakedata')
                query_time = time.time() - start_time
                
                results.append({
                    'worker_id': worker_id,
                    'query_num': i,
                    'symbol': symbol,
                    'success': error is None,
                    'result_count': len(df) if error is None else 0,
                    'query_time': query_time
                })
            
            return results
        
        # Run concurrent workers
        num_workers = 20
        all_results = []
        
        with ThreadPoolExecutor(max_workers=num_workers) as executor:
            future_to_worker = {
                executor.submit(worker_query, worker_id): worker_id
                for worker_id in range(num_workers)
            }
            
            for future in as_completed(future_to_worker):
                worker_results = future.result()
                all_results.extend(worker_results)
        
        # Analyze results
        total_queries = len(all_results)
        successful_queries = sum(1 for r in all_results if r['success'])
        avg_query_time = sum(r['query_time'] for r in all_results) / total_queries
        max_query_time = max(r['query_time'] for r in all_results)
        
        print(f"\\nConcurrent test results:")
        print(f"Total queries: {total_queries}")
        print(f"Successful: {successful_queries}")
        print(f"Success rate: {successful_queries/total_queries*100:.1f}%")
        print(f"Average query time: {avg_query_time:.4f}s")
        print(f"Max query time: {max_query_time:.4f}s")
        
        # Assertions
        assert successful_queries == total_queries, "Not all concurrent queries succeeded"
        assert avg_query_time < 0.1, f"Average concurrent query time too slow: {avg_query_time:.4f}s"
        assert max_query_time < 0.5, f"Max concurrent query time too slow: {max_query_time:.4f}s"
    
    @pytest.mark.slow
    @pytest.mark.integration
    def test_flask_concurrent_requests(self, app_with_test_db):
        """Test Flask app under concurrent HTTP requests - simplified version."""
        
        # Test concurrent requests by making sequential requests instead
        # Flask test client is not thread-safe, so we test basic functionality instead
        results = []
        
        for i in range(30):  # Test 30 sequential requests to simulate load
            # Alternate between different request types
            if i % 3 == 0:
                # Search request
                response = app_with_test_db.post('/search', data={
                    'tickers': 'AAPL',
                    'db_type': 'osakedata'
                })
            elif i % 3 == 1:
                # API request  
                response = app_with_test_db.get('/api/symbols?db_type=osakedata')
            else:
                # Index request
                response = app_with_test_db.get('/')
            
            results.append({
                'request_num': i,
                'status_code': response.status_code,
                'success': response.status_code == 200
            })
        
        # Analyze results
        total_requests = len(results)
        successful_requests = sum(1 for r in results if r['success'])
        
        print(f"\\nSequential HTTP test results:")
        print(f"Total requests: {total_requests}")
        print(f"Successful: {successful_requests}")
        print(f"Success rate: {successful_requests/total_requests*100:.1f}%")
        
        # All HTTP requests should succeed
        assert successful_requests == total_requests, f"HTTP requests failed: {total_requests - successful_requests}"
    
    @pytest.mark.slow
    @pytest.mark.db
    def test_mixed_read_write_operations(self, monkeypatch, test_osakedata_db):
        """Test mixed read and write operations under load."""
        monkeypatch.setattr('main.DB_PATHS', {'osakedata': test_osakedata_db})
        
        def reader_worker(worker_id):
            """Reader worker performing searches."""
            for i in range(20):
                df, error, found_symbols = get_stock_data(['AAPL'], 'osakedata')
                assert error is None or 'database is locked' in error  # Allow occasional lock errors
                time.sleep(0.001)  # Small delay
        
        def writer_worker(worker_id):
            """Writer worker performing deletions."""
            # Note: This is a destructive test, so we use symbols we can afford to lose
            test_symbols = ['DUP']  # Use duplicate entries from test data
            
            for i in range(5):
                success, message, count = delete_stock_data(test_symbols, 'osakedata')
                # Delete might fail if data already deleted by another worker
                time.sleep(0.002)  # Small delay
        
        # Run mixed read/write operations
        readers = []
        writers = []
        
        # Start reader threads
        for i in range(10):
            reader = threading.Thread(target=reader_worker, args=(i,))
            readers.append(reader)
            reader.start()
        
        # Start fewer writer threads to avoid too many conflicts
        for i in range(2):
            writer = threading.Thread(target=writer_worker, args=(i,))
            writers.append(writer)
            writer.start()
        
        # Wait for all to complete
        for reader in readers:
            reader.join(timeout=10)
        
        for writer in writers:
            writer.join(timeout=10)
        
        # Verify database is still functional after mixed operations
        df, error, found_symbols = get_stock_data(['AAPL'], 'osakedata')
        assert error is None
        assert not df.empty


class TestResourceCleanup:
    """Test suite for resource cleanup and leak detection."""
    
    @pytest.mark.slow
    @pytest.mark.db
    def test_database_connection_cleanup(self, monkeypatch, test_osakedata_db):
        """Test that database connections are properly cleaned up."""
        monkeypatch.setattr('main.DB_PATHS', {'osakedata': test_osakedata_db})
        
        # Get initial file descriptor count
        process = psutil.Process()
        initial_fd_count = process.num_fds() if hasattr(process, 'num_fds') else 0
        
        # Perform many operations that open database connections
        for i in range(100):
            df, error, found_symbols = get_stock_data(['AAPL'], 'osakedata')
            symbols = get_available_symbols('osakedata')
            
            # Occasionally perform deletes (which also use connections)
            if i % 20 == 0 and i > 0:
                # Try to delete non-existent symbol (safe operation)
                delete_stock_data(['NONEXISTENT_SYMBOL'], 'osakedata')
        
        # Check file descriptor count after operations
        final_fd_count = process.num_fds() if hasattr(process, 'num_fds') else 0
        
        # Allow some growth, but not excessive (connections should be closed)
        if initial_fd_count > 0:  # Only check if we can measure FDs
            fd_growth = final_fd_count - initial_fd_count
            assert fd_growth < 10, f"Too many file descriptors left open: {fd_growth}"
    
    @pytest.mark.slow
    @pytest.mark.db 
    def test_memory_leak_detection(self, monkeypatch, test_osakedata_db):
        """Test for memory leaks during repeated operations."""
        monkeypatch.setattr('main.DB_PATHS', {'osakedata': test_osakedata_db})
        
        process = psutil.Process()
        
        # Measure initial memory
        initial_memory = process.memory_info().rss / 1024 / 1024  # MB
        
        # Perform many operations
        for i in range(500):
            df, error, found_symbols = get_stock_data(['AAPL'], 'osakedata')
            symbols = get_available_symbols('osakedata')
            
            # Force some garbage collection periodically
            if i % 50 == 0:
                import gc
                gc.collect()
                
                # Check memory periodically
                current_memory = process.memory_info().rss / 1024 / 1024  # MB
                memory_growth = current_memory - initial_memory
                
                # Allow some growth, but not excessive
                assert memory_growth < 50, f"Excessive memory growth detected: {memory_growth:.2f}MB at iteration {i}"
        
        # Final memory check
        final_memory = process.memory_info().rss / 1024 / 1024  # MB
        total_growth = final_memory - initial_memory
        
        print(f"\\nMemory usage: Initial: {initial_memory:.2f}MB, Final: {final_memory:.2f}MB, Growth: {total_growth:.2f}MB")
        
        # Total growth should be reasonable
        assert total_growth < 100, f"Memory leak detected: {total_growth:.2f}MB growth"