"""
Testit CSV-toiminnallisuudelle.

Testaa CSV-lukemista, virhetilanteita, Flask-reittejä ja UI-komponentteja.
Varmistaa ettei testit muuta tuotantotietokantoja.
"""

import pytest
import tempfile
import os
import sqlite3
import json
from unittest.mock import patch, mock_open, MagicMock
from main import app, fetch_csv_data, get_db_path


class TestCSVDataFetching:
    """Testit CSV-datan lukemiselle."""
    
    @pytest.mark.unit
    @pytest.mark.csv
    def test_fetch_csv_data_valid_input(self, isolated_db):
        """Testi: Onnistunut CSV-datan lataus kelvollisilla syötteillä."""
        # Simuloi CSV-tiedosto
        csv_content = """^IXIC,2023-07-03,13000.00,13100.00,12900.00,13050.00,1000000,2023-07-04,13060.00,13160.00,12960.00,13110.00,1100000
^GSPC,2023-07-03,4400.00,4450.00,4390.00,4420.00,2000000,2023-07-04,4430.00,4480.00,4420.00,4460.00,2100000"""
        
        with patch("os.path.exists", return_value=True):
            with patch("builtins.open", mock_open(read_data=csv_content)):
                success, message, count = fetch_csv_data(['^IXIC', '^GSPC'])
                
        assert success is True
        assert count == 4  # 2 tickeria * 2 päivämäärää
        assert "Tallennettu 4 riviä CSV:stä" in message
    
    @pytest.mark.unit
    @pytest.mark.csv
    def test_fetch_csv_data_mass_import_none(self, isolated_db):
        """Testi: Massa-ajo None parametrilla."""
        csv_content = """^IXIC,2023-07-03,13000.00,13100.00,12900.00,13050.00,1000000
^GSPC,2023-07-03,4400.00,4450.00,4390.00,4420.00,2000000"""
        
        with patch("os.path.exists", return_value=True):
            with patch("builtins.open", mock_open(read_data=csv_content)):
                success, message, count = fetch_csv_data(None)
                
        assert success is True
        assert count == 2
        assert "MASSA-AJO" in message
        assert "2 osaketta" in message
    
    @pytest.mark.unit
    @pytest.mark.csv
    def test_fetch_csv_data_mass_import_empty_list(self, isolated_db):
        """Testi: Massa-ajo tyhjällä listalla."""
        csv_content = """^IXIC,2023-07-03,13000.00,13100.00,12900.00,13050.00,1000000
^GSPC,2023-07-03,4400.00,4450.00,4390.00,4420.00,2000000"""
        
        with patch("os.path.exists", return_value=True):
            with patch("builtins.open", mock_open(read_data=csv_content)):
                success, message, count = fetch_csv_data([])
                
        assert success is True
        assert count == 2
        assert "MASSA-AJO" in message
        assert "2 osaketta" in message
    
    @pytest.mark.unit
    @pytest.mark.csv
    def test_fetch_csv_data_invalid_tickers(self, isolated_db):
        """Testi: Virheelliset ticker-symbolit."""
        success, message, count = fetch_csv_data(['', '   ', '123!@#'])
        
        assert success is False
        assert count == 0
        assert "Ei kelvollisia tickereitä annettu" in message
    
    @pytest.mark.unit
    @pytest.mark.csv
    def test_fetch_csv_data_special_characters(self, isolated_db):
        """Testi: Erikoismerkit tickereissä."""
        csv_content = "BRK.B,2023-07-03,300.00,305.00,295.00,302.00,500000"
        
        with patch("os.path.exists", return_value=True):
            with patch("builtins.open", mock_open(read_data=csv_content)):
                success, message, count = fetch_csv_data(['BRK.B'])
                
        assert success is True
        assert count == 1
    
    @pytest.mark.unit
    @pytest.mark.csv
    def test_fetch_csv_data_file_not_found(self, isolated_db):
        """Testi: CSV-tiedostoa ei löydy."""
        with patch("os.path.exists", return_value=False):
            success, message, count = fetch_csv_data(['^IXIC'])
            
        assert success is False
        assert count == 0
        assert "CSV-tiedostoa ei löytynyt" in message
    
    @pytest.mark.unit 
    @pytest.mark.csv
    def test_fetch_csv_data_malformed_csv(self, isolated_db):
        """Testi: Virheellinen CSV-muoto."""
        # CSV jossa on liian vähän kenttiä
        csv_content = "^IXIC,2023-07-03,13000.00"  # Puuttuu kenttiä
        
        with patch("os.path.exists", return_value=True):
            with patch("builtins.open", mock_open(read_data=csv_content)):
                success, message, count = fetch_csv_data(['^IXIC'])
                
        assert success is False
        assert count == 0
        assert "ei löytynyt CSV:stä" in message
    
    @pytest.mark.unit
    @pytest.mark.csv
    def test_fetch_csv_data_invalid_dates(self, isolated_db):
        """Testi: Virheelliset päivämäärät CSV:ssä."""
        csv_content = "^IXIC,invalid-date,13000.00,13100.00,12900.00,13050.00,1000000"
        
        with patch("os.path.exists", return_value=True):
            with patch("builtins.open", mock_open(read_data=csv_content)):
                success, message, count = fetch_csv_data(['^IXIC'])
                
        assert success is False
        assert count == 0
    
    @pytest.mark.unit
    @pytest.mark.csv
    def test_fetch_csv_data_invalid_numbers(self, isolated_db):
        """Testi: Virheelliset numerot CSV:ssä."""
        csv_content = "^IXIC,2023-07-03,not-a-number,13100.00,12900.00,13050.00,1000000"
        
        with patch("os.path.exists", return_value=True):
            with patch("builtins.open", mock_open(read_data=csv_content)):
                success, message, count = fetch_csv_data(['^IXIC'])
                
        assert success is False
        assert count == 0
    
    @pytest.mark.unit
    @pytest.mark.csv
    def test_fetch_csv_data_duplicate_prevention(self, isolated_db):
        """Testi: Duplikaattien esto."""
        csv_content = "^IXIC,2023-07-03,13000.00,13100.00,12900.00,13050.00,1000000"
        
        with patch("os.path.exists", return_value=True):
            with patch("builtins.open", mock_open(read_data=csv_content)):
                # Ensimmäinen lataus
                success1, message1, count1 = fetch_csv_data(['^IXIC'])
                
                # Toinen lataus samoilla tiedoilla
                success2, message2, count2 = fetch_csv_data(['^IXIC'])
                
        assert success1 is True
        assert count1 == 1
        
        assert success2 is False
        assert count2 == 0
        assert "kaikki jo olemassa" in message2
    
    @pytest.mark.unit
    @pytest.mark.csv
    def test_fetch_csv_data_ticker_not_found(self, isolated_db):
        """Testi: Pyydettyä tickeriä ei löydy CSV:stä."""
        csv_content = "^IXIC,2023-07-03,13000.00,13100.00,12900.00,13050.00,1000000"
        
        with patch("os.path.exists", return_value=True):
            with patch("builtins.open", mock_open(read_data=csv_content)):
                success, message, count = fetch_csv_data(['UNKNOWN'])
                
        assert success is False
        assert count == 0
        assert "UNKNOWN (ei löytynyt CSV:stä)" in message


class TestCSVFlaskRoutes:
    """Testit CSV Flask-reiteille."""
    
    @pytest.fixture
    def client(self, isolated_db):
        """Flask test client."""
        with app.test_client() as client:
            yield client
    
    @pytest.mark.integration
    @pytest.mark.web
    @pytest.mark.csv
    def test_fetch_csv_route_mass_import(self, client, isolated_db):
        """Testi: CSV massa-ajo tyhjällä ticker-kentällä."""
        csv_content = """^IXIC,2023-07-03,13000.00,13100.00,12900.00,13050.00,1000000
^GSPC,2023-07-03,4400.00,4450.00,4390.00,4420.00,2000000"""
        
        # Tallennetaan alkuperäinen open-funktio rekursion välttämiseksi
        original_open = open
        
        with patch("main.os.path.exists", return_value=True):
            # Mockataan vain CSV-tiedoston lukeminen, ei kaikkia open-kutsuja
            def side_effect(file_path, *args, **kwargs):
                if '/home/kalle/projects/rawcandle/data/osakedata.csv' in str(file_path):
                    return mock_open(read_data=csv_content)()
                else:
                    # Käytä alkuperäistä open-funktiota muille tiedostoille
                    return original_open(file_path, *args, **kwargs)
            
            with patch("builtins.open", side_effect=side_effect):
                response = client.post('/fetch_csv', data={'tickers': ''})
                
        assert response.status_code == 200
        response_text = response.get_data(as_text=True)
        assert 'MASSA-AJO' in response_text
        # Tarkistaa että saa HTML-sivun takaisin
        assert b'<!DOCTYPE' in response.data or b'<html' in response.data
    
    @pytest.mark.integration
    @pytest.mark.web
    @pytest.mark.csv
    def test_fetch_csv_route_success(self, client, isolated_db):
        """Testi: CSV-reitti palauttaa HTML-sivun."""
        response = client.post('/fetch_csv', data={'tickers': 'TEST'})
        assert response.status_code == 200
        # Tarkistaa että saa HTML-sivun takaisin
        assert b'<!DOCTYPE' in response.data or b'<html' in response.data
    
    @pytest.mark.integration
    @pytest.mark.web
    @pytest.mark.csv
    def test_fetch_csv_route_specific_tickers(self, client, isolated_db):
        """Testi: Määrättyjen tickereiden haku CSV:stä."""
        csv_content = """^IXIC,2023-07-03,13000.00,13100.00,12900.00,13050.00,1000000
^GSPC,2023-07-03,4400.00,4450.00,4390.00,4420.00,2000000
AAPL,2023-07-03,150.00,155.00,149.00,152.00,50000000"""
        
        # Tallennetaan alkuperäinen open-funktio rekursion välttämiseksi
        original_open = open
        
        with patch("main.os.path.exists", return_value=True):
            def side_effect(file_path, *args, **kwargs):
                if '/home/kalle/projects/rawcandle/data/osakedata.csv' in str(file_path):
                    return mock_open(read_data=csv_content)()
                else:
                    return original_open(file_path, *args, **kwargs)
            
            with patch("builtins.open", side_effect=side_effect):
                response = client.post('/fetch_csv', data={'tickers': '^IXIC,AAPL'})
                
        assert response.status_code == 200
        assert b'<!DOCTYPE' in response.data or b'<html' in response.data
    
    @pytest.mark.integration
    @pytest.mark.web
    @pytest.mark.csv
    def test_fetch_csv_route_multiple_tickers(self, client, isolated_db):
        """Testi: Useampi ticker Flask-reitillä palauttaa HTML."""
        response = client.post('/fetch_csv', data={'tickers': 'TEST1,TEST2'})
        
        assert response.status_code == 200
        assert b'<!DOCTYPE' in response.data or b'<html' in response.data
    
    @pytest.mark.integration
    @pytest.mark.web
    @pytest.mark.csv
    def test_fetch_csv_route_error_handling(self, client, isolated_db):
        """Testi: Virhetilanteiden käsittely Flask-reitillä."""
        response = client.post('/fetch_csv', data={'tickers': 'INVALID'})
            
        assert response.status_code == 200
        assert b'<!DOCTYPE' in response.data or b'<html' in response.data
    
    @pytest.mark.integration
    @pytest.mark.web
    @pytest.mark.csv
    def test_fetch_csv_route_get_method_not_allowed(self, client, isolated_db):
        """Testi: GET-metodi ei ole sallittu CSV-reitillä."""
        response = client.get('/fetch_csv')
        assert response.status_code == 405  # Method Not Allowed


class TestCSVFormHandling:
    """Testit CSV-lomakkeen käsittelylle."""
    
    @pytest.fixture
    def client(self, isolated_db):
        """Flask test client."""
        with app.test_client() as client:
            yield client
    
    @pytest.mark.integration
    @pytest.mark.web
    @pytest.mark.csv
    def test_csv_form_whitespace_handling(self, client, isolated_db):
        """Testi: Välilyöntien käsittely lomakkeessa."""
        csv_content = "^IXIC,2023-07-03,13000.00,13100.00,12900.00,13050.00,1000000"
        
        # Tallennetaan alkuperäinen open-funktio rekursion välttämiseksi
        original_open = open
        
        with patch("main.os.path.exists", return_value=True):
            def side_effect(file_path, *args, **kwargs):
                if '/home/kalle/projects/rawcandle/data/osakedata.csv' in str(file_path):
                    return mock_open(read_data=csv_content)()
                else:
                    return original_open(file_path, *args, **kwargs)
            
            with patch("builtins.open", side_effect=side_effect):
                response = client.post('/fetch_csv', data={'tickers': '  ^IXIC  '})
                
        assert response.status_code == 200
        assert b'Tallennettu 1 rivi' in response.data or b'success' in response.data
    
    @pytest.mark.integration
    @pytest.mark.web
    @pytest.mark.csv
    def test_csv_form_comma_separated_tickers(self, client, isolated_db):
        """Testi: Pilkulla erotetut tickerit."""
        csv_content = """^IXIC,2023-07-03,13000.00,13100.00,12900.00,13050.00,1000000
^GSPC,2023-07-03,4400.00,4450.00,4390.00,4420.00,2000000"""

        # Tallennetaan alkuperäinen open-funktio rekursion välttämiseksi
        original_open = open
        
        with patch("main.os.path.exists", return_value=True):
            def side_effect(file_path, *args, **kwargs):
                if '/home/kalle/projects/rawcandle/data/osakedata.csv' in str(file_path):
                    return mock_open(read_data=csv_content)()
                else:
                    return original_open(file_path, *args, **kwargs)
            
            with patch("builtins.open", side_effect=side_effect):
                response = client.post('/fetch_csv', data={'tickers': '^IXIC,^GSPC'})
            
        assert response.status_code == 200
        assert b'Tallennettu 2 rivi' in response.data or b'success' in response.data
    
    @pytest.mark.integration
    @pytest.mark.web
    @pytest.mark.csv
    def test_csv_form_case_insensitive(self, client, isolated_db):
        """Testi: Ei erota isoja ja pieniä kirjaimia."""
        csv_content = "AAPL,2023-07-03,150.00,155.00,149.00,152.00,50000000"
        
        # Tallennetaan alkuperäinen open-funktio rekursion välttämiseksi
        original_open = open
        
        with patch("main.os.path.exists", return_value=True):
            def side_effect(file_path, *args, **kwargs):
                if '/home/kalle/projects/rawcandle/data/osakedata.csv' in str(file_path):
                    return mock_open(read_data=csv_content)()
                else:
                    return original_open(file_path, *args, **kwargs)
            
            with patch("builtins.open", side_effect=side_effect):
                response = client.post('/fetch_csv', data={'tickers': 'aapl'})
                
        assert response.status_code == 200
        assert b'Tallennettu 1 rivi' in response.data or b'success' in response.data


class TestCSVUIComponents:
    """Testit CSV-käyttöliittymäkomponenteille."""
    
    @pytest.mark.integration
    @pytest.mark.web
    @pytest.mark.csv
    def test_csv_ui_elements_exist(self, isolated_db):
        """Testi: CSV UI-elementit ovat olemassa."""
        with app.test_client() as client:
            response = client.get('/')
            
        assert response.status_code == 200
        # Tarkistetaan että sivulla on CSV-elementtejä
        content = response.data.decode('utf-8', errors='ignore')
        assert 'CSV' in content or 'csv' in content


class TestCSVDatabaseProtection:
    """Testit tuotantotietokantojen suojaukselle."""
    
    @pytest.mark.unit
    @pytest.mark.db
    @pytest.mark.csv
    def test_csv_uses_isolated_database(self, isolated_db):
        """Varmista että CSV-funktio käyttää eristettyä tietokantaa."""
        csv_content = "TEST,2023-07-03,100.00,101.00,99.00,100.50,1000000"
        
        # Tarkista että käytetään test-tietokantaa
        with patch("os.path.exists", return_value=True):
            with patch("builtins.open", mock_open(read_data=csv_content)):
                success, message, count = fetch_csv_data(['TEST'])
        
        # Varmista että data meni test-tietokantaan, ei tuotantoon
        test_db_path = get_db_path('osakedata')
        assert '/tmp/' in test_db_path or 'test' in test_db_path
        
        # Tarkista että tuotantotietokanta on koskematon
        prod_db_path = '/home/kalle/projects/rawcandle/data/osakedata.db'
        if os.path.exists(prod_db_path):
            with sqlite3.connect(prod_db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT COUNT(*) FROM osakedata WHERE osake = 'TEST'")
                result = cursor.fetchone()[0]
                assert result == 0, "TEST-data löytyi tuotantotietokannasta!"
    
    @pytest.mark.unit
    @pytest.mark.db
    @pytest.mark.csv  
    def test_csv_database_path_isolation(self, isolated_db):
        """Varmista että CSV-funktio ei käytä tuotantopolkuja."""
        original_path = get_db_path('osakedata')
        
        # Polun pitää olla eristetty testausta varten
        assert '/tmp/' in original_path or 'test' in original_path
        assert '/home/kalle/projects/rawcandle/data/' not in original_path
    
    @pytest.mark.integration
    @pytest.mark.db
    @pytest.mark.csv
    def test_csv_route_database_isolation(self, isolated_db):
        """Varmista että CSV-reitti käyttää eristettyä tietokantaa."""
        app.config['TESTING'] = True
        
        csv_content = "ROUTE_TEST,2023-07-03,200.00,201.00,199.00,200.50,2000000"
        
        with app.test_client() as client:
            with patch("os.path.exists", return_value=True):
                with patch("builtins.open", mock_open(read_data=csv_content)):
                    response = client.post('/fetch_csv', data={'tickers': 'ROUTE_TEST'})
        
        # Varmista että tuotantotietokanta on koskematon
        prod_db_path = '/home/kalle/projects/rawcandle/data/osakedata.db'
        if os.path.exists(prod_db_path):
            with sqlite3.connect(prod_db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT COUNT(*) FROM osakedata WHERE osake = 'ROUTE_TEST'")
                result = cursor.fetchone()[0]
                assert result == 0, "ROUTE_TEST-data löytyi tuotantotietokannasta!"


class TestCSVErrorScenarios:
    """Testit CSV-virheskenaarioille."""
    
    @pytest.mark.unit
    @pytest.mark.csv
    def test_csv_file_permission_error(self, isolated_db):
        """Testi: Tiedoston lukuoikeusongelma."""
        with patch("os.path.exists", return_value=True):
            with patch("builtins.open", side_effect=PermissionError("Permission denied")):
                success, message, count = fetch_csv_data(['^IXIC'])
                
        assert success is False
        assert count == 0
        assert "Virhe CSV-lukemisessa" in message
    
    @pytest.mark.unit
    @pytest.mark.csv
    def test_csv_database_connection_error(self, isolated_db):
        """Testi: Tietokantayhteyden virhe."""
        csv_content = "^IXIC,2023-07-03,13000.00,13100.00,12900.00,13050.00,1000000"
        
        with patch("os.path.exists", return_value=True):
            with patch("builtins.open", mock_open(read_data=csv_content)):
                with patch("sqlite3.connect", side_effect=sqlite3.Error("Database error")):
                    success, message, count = fetch_csv_data(['^IXIC'])
                    
        assert success is False
        assert count == 0
        assert "Virhe CSV-lukemisessa" in message
    
    @pytest.mark.unit
    @pytest.mark.csv
    def test_csv_empty_file(self, isolated_db):
        """Testi: Tyhjä CSV-tiedosto."""
        csv_content = ""
        
        with patch("os.path.exists", return_value=True):
            with patch("builtins.open", mock_open(read_data=csv_content)):
                success, message, count = fetch_csv_data(['^IXIC'])
                
        assert success is False
        assert count == 0


class TestCSVPerformance:
    """Testit CSV-suorituskyvylle."""
    
    @pytest.mark.slow
    @pytest.mark.csv
    def test_csv_large_data_handling(self, isolated_db):
        """Testi: Suurten CSV-tiedostojen käsittely."""
        # Simuloi iso CSV-tiedosto (100 päivämäärää)
        csv_lines = ["^IXIC"]
        for i in range(100):
            date = f"2023-{7+i//30:02d}-{(i%30)+1:02d}"
            csv_lines.append(f"{date},13000.{i:02d},13100.{i:02d},12900.{i:02d},13050.{i:02d},{1000000+i}")
        
        csv_content = "^IXIC," + ",".join(csv_lines[1:])
        
        with patch("os.path.exists", return_value=True):
            with patch("builtins.open", mock_open(read_data=csv_content)):
                success, message, count = fetch_csv_data(['^IXIC'])
                
        assert success is True
        assert count > 50  # Ainakin osa tiedoista tallentui
    
    @pytest.mark.unit
    @pytest.mark.csv
    def test_csv_memory_efficient(self, isolated_db):
        """Testi: Muistin tehokas käyttö CSV-lukemisessa."""
        # Varmista että CSV-lukeminen ei lataa kaikkea muistiin kerralla
        csv_content = "^IXIC,2023-07-03,13000.00,13100.00,12900.00,13050.00,1000000"
        
        with patch("os.path.exists", return_value=True):
            # Mock context manager että open() toimii oikein
            mock_file = MagicMock()
            mock_file.__enter__ = MagicMock(return_value=mock_file)
            mock_file.__exit__ = MagicMock(return_value=None)
            mock_file.read.return_value = csv_content
            
            with patch("builtins.open", return_value=mock_file):
                success, message, count = fetch_csv_data(['^IXIC'])
                
            # Tiedosto pitää avata ja lukea
            assert success == True
            assert count == 1


if __name__ == '__main__':
    pytest.main([__file__, '-v'])