#!/usr/bin/env python3
"""
Stock Data Web Viewer
A Flask web application for viewing stock data from SQLite database.
"""

from flask import Flask, render_template, request, jsonify
import sqlite3
import pandas as pd
import os
import yfinance as yf
from datetime import datetime

app = Flask(__name__)

# Tietokantojen sijainnit
DB_PATHS = {
    'osakedata': "/home/kalle/projects/rawcandle/data/osakedata.db",
    'analysis': "/home/kalle/projects/rawcandle/analysis/analysis.db"
}

def get_db_path(db_type):
    """Palauta valitun tietokannan polku."""
    if db_type not in DB_PATHS:
        # Testien aikana DB_PATHS voi olla vaillinainen
        return '/tmp/dummy.db'
    return DB_PATHS[db_type]

def get_db_label(db_type):
    """Palauta tietokannan selkokielinen nimi."""
    labels = {
        'osakedata': 'Osakedata (OHLCV)',
        'analysis': 'Kynttiläkuvioanalyysi'
    }
    return labels.get(db_type, 'Tuntematon')

def get_stock_data(search_terms, db_type='osakedata'):
    """
    Hae data tietokannasta. Tukee sekä tarkkaa hakua että osittaista hakua.
    
    Args:
        search_terms (list): Lista hakutermeistä (voivat olla tarkkoja symboleja tai alkuja)
        db_type (str): Tietokannan tyyppi ('osakedata' tai 'analysis')
    
    Returns:
        pandas.DataFrame: Data tietokannasta
        str: Virheviesti tai None
        list: Löytyneet symbolit/tickerit
    """
    db_path = get_db_path(db_type)
    if not os.path.exists(db_path):
        return pd.DataFrame(), f"Tietokanta ei löydy: {db_path}", []
    
    try:
        # Määrittele kysely tietokantatyypin mukaan
        if db_type == 'analysis':
            # Analysis-tietokanta: id, ticker, date, candle
            conditions = []
            params = []
            
            for term in search_terms:
                # Lisää sekä tarkka että osittainen haku tickerille
                conditions.append("(ticker = ? OR ticker LIKE ?)")
                params.append(term)
                params.append(f"{term}%")
            
            where_clause = " OR ".join(conditions)
            query = f"""
                SELECT * FROM analysis_findings 
                WHERE {where_clause}
                ORDER BY ticker, date DESC
            """
        else:
            # Osakedata-tietokanta: osake, pvm, open, high, low, close, volume
            conditions = []
            params = []
            
            for term in search_terms:
                # Lisää sekä tarkka että osittainen haku (alkaa termillä)
                conditions.append("(osake = ? OR osake LIKE ?)")
                params.append(term)
                params.append(f"{term}%")  # LIKE-haku joka alkaa termillä
            
            where_clause = " OR ".join(conditions)
            query = f"""
                SELECT * FROM osakedata 
                WHERE {where_clause}
                ORDER BY osake, pvm DESC
            """
        
        with sqlite3.connect(db_path) as conn:
            df = pd.read_sql_query(query, conn, params=params)
        
        # Hae löytyneet uniikit symbolit/tickerit
        if db_type == 'analysis':
            symbol_col = 'ticker'
            found_symbols = df[symbol_col].unique().tolist() if not df.empty else []
        else:
            symbol_col = 'osake'
            found_symbols = df[symbol_col].unique().tolist() if not df.empty else []
        
        if df.empty:
            return df, f"Ei löytynyt tietoja hakutermeille: {', '.join(search_terms)}", []
        
        return df, None, found_symbols
        
    except Exception as e:
        return pd.DataFrame(), f"Virhe tietokannasta hakiessa: {str(e)}", []

def get_available_symbols(db_type='osakedata'):
    """
    Hae kaikki saatavilla olevat symbolit/tickerit tietokannasta.
    Optimoitu suurille tietomäärille (10,000+ symbolia).
    """
    db_path = get_db_path(db_type)
    if not os.path.exists(db_path):
        return []
    
    try:
        with sqlite3.connect(db_path) as conn:
            # Optimoi connection suurille kyselyille
            conn.execute("PRAGMA cache_size = -64000")  # 64MB cache
            conn.execute("PRAGMA temp_store = MEMORY")
            
            cursor = conn.cursor()
            
            if db_type == 'analysis':
                # Käytä indeksiä jos se on olemassa
                cursor.execute("""
                    SELECT DISTINCT ticker 
                    FROM analysis_findings 
                    WHERE ticker IS NOT NULL AND ticker != ''
                    ORDER BY ticker
                """)
            else:
                # Käytä indeksiä jos se on olemassa  
                cursor.execute("""
                    SELECT DISTINCT osake 
                    FROM osakedata 
                    WHERE osake IS NOT NULL AND osake != ''
                    ORDER BY osake COLLATE NOCASE
                """)
            
            symbols = [row[0] for row in cursor.fetchall()]
            
        # Poista mahdolliset tyhjät arvot ja duplikaatit (varmistuksena)
        symbols = list(filter(None, symbols))
        
        app.logger.info(f"Loaded {len(symbols)} symbols from {db_type} database")
        return symbols
        
    except Exception as e:
        app.logger.error(f"Virhe symbolien hakemisessa {db_type}: {e}")
        return []

def delete_stock_data(symbols_to_delete, db_type='osakedata'):
    """
    Poista data tietokannasta annetuille symboleille/tickereille.
    
    Args:
        symbols_to_delete (list): Lista poistettavista symboleista/tickereistä
        db_type (str): Tietokannan tyyppi ('osakedata' tai 'analysis')
    
    Returns:
        tuple: (onnistui (bool), viesti (str), poistettujen_rivien_määrä (int))
    """
    db_path = get_db_path(db_type)
    if not os.path.exists(db_path):
        return False, f"Tietokanta ei löydy: {db_path}", 0
    
    try:
        with sqlite3.connect(db_path) as conn:
            cursor = conn.cursor()
            
            # Määrittele kyselyt tietokantatyypin mukaan
            placeholders = ','.join('?' * len(symbols_to_delete))
            if db_type == 'analysis':
                count_query = f"SELECT COUNT(*) FROM analysis_findings WHERE ticker IN ({placeholders})"
                delete_query = f"DELETE FROM analysis_findings WHERE ticker IN ({placeholders})"
            else:
                count_query = f"SELECT COUNT(*) FROM osakedata WHERE osake IN ({placeholders})"
                delete_query = f"DELETE FROM osakedata WHERE osake IN ({placeholders})"
            
            # Laske ensin montako riviä poistetaan
            cursor.execute(count_query, symbols_to_delete)
            rows_to_delete = cursor.fetchone()[0]
            
            if rows_to_delete == 0:
                return False, f"Ei löytynyt poistettavia rivejä symboleille: {', '.join(symbols_to_delete)}", 0
            
            # Poista rivit
            cursor.execute(delete_query, symbols_to_delete)
            conn.commit()
            
            return True, f"Poistettu {rows_to_delete} riviä symboleille: {', '.join(symbols_to_delete)}", rows_to_delete
            
    except Exception as e:
        return False, f"Virhe tietojen poistossa: {str(e)}", 0

def clear_database(db_type='osakedata'):
    """
    Tyhjentää koko tietokannan - VAARALLINEN TOIMINTO!
    
    Args:
        db_type (str): Tietokannan tyyppi ('osakedata' tai 'analysis' tai 'both')
    
    Returns:
        tuple: (onnistui (bool), viesti (str), poistettujen_rivien_määrä (int))
    """
    if db_type == 'both':
        # Tyhjennä molemmat tietokannat
        success1, msg1, count1 = clear_database('osakedata')
        success2, msg2, count2 = clear_database('analysis') 
        
        if success1 and success2:
            return True, f"Molemmat tietokannat tyhjennetty. {msg1} {msg2}", count1 + count2
        else:
            return False, f"Virhe tietokantoja tyhjentäessä: {msg1} {msg2}", count1 + count2
    
    db_path = get_db_path(db_type)
    if not os.path.exists(db_path):
        return False, f"Tietokanta ei löydy: {db_path}", 0
    
    try:
        with sqlite3.connect(db_path) as conn:
            cursor = conn.cursor()
            
            # Määrittele taulun nimi tietokantatyypin mukaan
            if db_type == 'analysis':
                table_name = 'analysis_findings'
            else:
                table_name = 'osakedata'
            
            # Laske rivien määrä ennen poistoa
            cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
            total_rows = cursor.fetchone()[0]
            
            if total_rows == 0:
                return True, f"Tietokanta {db_type} oli jo tyhjä", 0
            
            # Tyhjennä taulu
            cursor.execute(f"DELETE FROM {table_name}")
            
            # Nollaa autoincrement sekvenssi jos sqlite_sequence taulu on olemassa
            try:
                cursor.execute(f"DELETE FROM sqlite_sequence WHERE name='{table_name}'")
            except sqlite3.OperationalError:
                # sqlite_sequence ei ole olemassa - ei haittaa
                pass
            
            conn.commit()
            
            return True, f"Tietokanta {db_type} tyhjennetty ({total_rows} riviä poistettu)", total_rows
            
    except Exception as e:
        return False, f"Virhe tietokannan tyhjentämisessä: {str(e)}", 0


def fetch_yfinance_data(tickers):
    """
    Hae OHLCV-data Yahoo Financesta annetuille tickereille.
    Hakujakso: 1.7.2023 - 30.9.2025
    Palauttaa (success, message, saved_count)
    """
    if not isinstance(tickers, list):
        tickers = [tickers]
    
    # Siivoa ja yhdistele tickerit
    clean_tickers = [ticker.strip().upper() for ticker in tickers if ticker.strip()]
    
    if not clean_tickers:
        return False, "Ei kelvollisia tickereitä annettu", 0
    
    saved_count = 0
    failed_tickers = []
    
    # Hakujakso: 1.7.2023 - 30.9.2025
    start_date = "2023-07-01"
    end_date = "2025-09-30"
    
    db_path = get_db_path('osakedata')
    
    try:
        with sqlite3.connect(db_path) as conn:
            cursor = conn.cursor()
            
            # Varmista että taulu on olemassa
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
            
            # Varmista UNIQUE-indeksi duplikaattien estämiseksi
            cursor.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_osake_pvm ON osakedata(osake, pvm)")
            
            for ticker in clean_tickers:
                try:
                    # Hae data YFinancesta
                    stock = yf.Ticker(ticker)
                    hist = stock.history(start=start_date, end=end_date)
                    
                    # Tarkista että dataa löytyi
                    if hist.empty:
                        failed_tickers.append(f"{ticker} (ei dataa)")
                        continue
                    
                    # Käsittele data
                    hist.reset_index(inplace=True)
                    
                    # Tallenna rivit tietokantaan
                    ticker_saved = 0
                    for _, row in hist.iterrows():
                        # Ohita rivit joissa on NaN-arvoja
                        if pd.isna([row['Open'], row['High'], row['Low'], row['Close'], row['Volume']]).any():
                            continue
                        
                        date_str = row['Date'].strftime('%Y-%m-%d')
                        
                        # Tarkista onko päivämäärä jo olemassa
                        cursor.execute(
                            "SELECT COUNT(*) FROM osakedata WHERE osake = ? AND pvm = ?",
                            (ticker, date_str)
                        )
                        
                        if cursor.fetchone()[0] == 0:  # Ei ole olemassa
                            cursor.execute("""
                                INSERT INTO osakedata (osake, pvm, open, high, low, close, volume)
                                VALUES (?, ?, ?, ?, ?, ?, ?)
                            """, (
                                ticker,
                                date_str,
                                float(row['Open']),
                                float(row['High']),
                                float(row['Low']),
                                float(row['Close']),
                                int(row['Volume'])
                            ))
                            ticker_saved += 1
                    
                    if ticker_saved > 0:
                        saved_count += ticker_saved
                    else:
                        failed_tickers.append(f"{ticker} (kaikki päivät jo olemassa)")
                        
                except Exception as e:
                    failed_tickers.append(f"{ticker} (virhe: {str(e)})")
                    continue
            
            conn.commit()
            
            # Muodosta vastausviesti
            if saved_count > 0:
                success_msg = f"Tallennettu {saved_count} riviä"
                if failed_tickers:
                    return True, f"{success_msg}. Epäonnistui: {', '.join(failed_tickers)}", saved_count
                else:
                    return True, success_msg, saved_count
            else:
                if failed_tickers:
                    return False, f"Ei tallennettu yhtään riviä. Epäonnistui: {', '.join(failed_tickers)}", 0
                else:
                    return False, "Ei tallennettu yhtään riviä", 0
                    
    except Exception as e:
        return False, f"Tietokantavirhe: {str(e)}", 0


def fetch_tickers_from_file():
    """
    Hae tickers.txt tiedostosta kaikki tickerit ja lataa niiden YFinance data.
    Tiedosto: /home/kalle/projects/rawcandle/data/tickers.txt
    Hakujakso: 1.7.2023 - 30.9.2025
    Palauttaa (success, message, saved_count)
    """
    import time
    import os
    
    tickers_file = "/home/kalle/projects/rawcandle/data/tickers.txt"
    
    # Tarkista että tiedosto on olemassa
    if not os.path.exists(tickers_file):
        return False, f"Tickers-tiedostoa ei löytynyt: {tickers_file}", {'processed': 0, 'success_count': 0, 'error_count': 0, 'total_saved': 0}
    
    # Lue tickerit tiedostosta
    try:
        with open(tickers_file, 'r', encoding='utf-8') as f:
            all_tickers = [line.strip().upper() for line in f if line.strip()]
    except Exception as e:
        return False, f"Virhe tickers-tiedoston lukemisessa: {str(e)}", {'processed': 0, 'success_count': 0, 'error_count': 0, 'total_saved': 0}
    
    if not all_tickers:
        return False, "Tickers-tiedosto on tyhjä", {'processed': 0, 'success_count': 0, 'error_count': 0, 'total_saved': 0}
    
    print(f"📁 Luettu {len(all_tickers)} tickeriä tiedostosta")
    
    total_saved = 0
    failed_tickers = []
    processed_count = 0
    
    # Hakujakso: sama kuin fetch_yfinance_data
    start_date = "2023-07-01"
    end_date = "2025-09-30"
    
    db_path = get_db_path('osakedata')
    
    try:
        with sqlite3.connect(db_path) as conn:
            cursor = conn.cursor()
            
            # Varmista että taulu on olemassa
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
            
            # Varmista UNIQUE-indeksi duplikaattien estämiseksi
            cursor.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_osake_pvm ON osakedata(osake, pvm)")
            
            for i, ticker in enumerate(all_tickers, 1):
                processed_count = i
                print(f"🔄 Haetaan {ticker} ({i}/{len(all_tickers)})")
                
                try:
                    # Hae data YFinancesta
                    stock = yf.Ticker(ticker)
                    hist = stock.history(start=start_date, end=end_date)
                    
                    # Tarkista että dataa löytyi
                    if hist.empty:
                        failed_tickers.append(f"{ticker} (ei dataa)")
                        print(f"   ❌ {ticker}: Ei dataa")
                    else:
                        # Käsittele data
                        hist.reset_index(inplace=True)
                        
                        # Tallenna rivit tietokantaan
                        ticker_saved = 0
                        for _, row in hist.iterrows():
                            # Ohita rivit joissa on NaN-arvoja
                            if pd.isna([row['Open'], row['High'], row['Low'], row['Close'], row['Volume']]).any():
                                continue
                            
                            date_str = row['Date'].strftime('%Y-%m-%d')
                            
                            # Tarkista onko päivämäärä jo olemassa
                            cursor.execute(
                                "SELECT COUNT(*) FROM osakedata WHERE osake = ? AND pvm = ?",
                                (ticker, date_str)
                            )
                            
                            if cursor.fetchone()[0] == 0:  # Ei ole olemassa
                                cursor.execute("""
                                    INSERT INTO osakedata (osake, pvm, open, high, low, close, volume)
                                    VALUES (?, ?, ?, ?, ?, ?, ?)
                                """, (
                                    ticker,
                                    date_str,
                                    float(row['Open']),
                                    float(row['High']),
                                    float(row['Low']),
                                    float(row['Close']),
                                    int(row['Volume'])
                                ))
                                ticker_saved += 1
                        
                        if ticker_saved > 0:
                            total_saved += ticker_saved
                            print(f"   ✅ {ticker}: {ticker_saved} riviä tallennettu")
                        else:
                            failed_tickers.append(f"{ticker} (kaikki päivät jo olemassa)")
                            print(f"   ⚠️ {ticker}: Kaikki päivät jo olemassa")
                            
                except Exception as e:
                    failed_tickers.append(f"{ticker} (virhe: {str(e)})")
                    print(f"   ❌ {ticker}: Virhe - {str(e)}")
                
                # 1 sekunnin tauko jokaisen osakkeen jälkeen
                if i < len(all_tickers):  # Ei taukoa viimeisen jälkeen
                    time.sleep(1)
                
                # 10 sekunnin tauko joka 100. osakkeen jälkeen
                if i % 100 == 0 and i < len(all_tickers):
                    print(f"⏸️ 10s tauko ({i}/100 osaketta haettu)")
                    time.sleep(10)
                
                # Commitoi muutokset säännöllisesti
                if i % 10 == 0:
                    conn.commit()
            
            # Lopullinen commit
            conn.commit()
            
            # Muodosta vastausviesti ja statistiikat
            success_count = processed_count - len(failed_tickers)
            success_msg = f"Käsitelty {processed_count}/{len(all_tickers)} tickeriä. Tallennettu {total_saved} riviä."
            
            if failed_tickers and len(failed_tickers) < 20:  # Näytä epäonnistumiset jos ei liian monta
                success_msg += f" Epäonnistui: {', '.join(failed_tickers[:10])}"
                if len(failed_tickers) > 10:
                    success_msg += f" (+{len(failed_tickers)-10} muuta)"
            elif failed_tickers:
                success_msg += f" Epäonnistui: {len(failed_tickers)} tickeriä"
            
            stats = {
                'processed': processed_count,
                'success_count': success_count,
                'error_count': len(failed_tickers),
                'total_saved': total_saved
            }
            
            return True, success_msg, stats
            
    except Exception as e:
        error_msg = f"Tietokantavirhe tickeritiedoston käsittelyssä: {str(e)}"
        print(f"❌ {error_msg}")
        stats = {
            'processed': processed_count,
            'success_count': 0,
            'error_count': processed_count,
            'total_saved': total_saved
        }
        return False, error_msg, stats


def fetch_csv_data(tickers=None):
    """
    Lataa osaketiedot CSV-tiedostosta /home/kalle/projects/rawcandle/data/osakedata.csv
    
    MASSA-AJO: Jos tickers=None tai tyhjä, ladataan KAIKKI CSV:ssä olevat osakkeet.
    Jos tickers annettu, ladataan vain ne tickerit.
    """
    import csv
    from datetime import datetime
    
    # Massa-ajo: Jos ei tickereitä annettu, ladataan kaikki CSV:stä
    mass_import = not tickers or (isinstance(tickers, list) and not any(tickers))
    
    if not mass_import:
        # Siivoa ja validoi tickerit vain jos ei massa-ajoa
        clean_tickers = []
        for ticker in tickers:
            ticker = ticker.strip().upper()
            if ticker and ticker.replace('.', '').replace('-', '').replace('^', '').isalnum():
                clean_tickers.append(ticker)
        
        if not clean_tickers:
            return False, "Ei kelvollisia tickereitä annettu", 0
    else:
        clean_tickers = None  # Massa-ajossa ei rajoiteta tickereitä
    
    csv_file_path = "/home/kalle/projects/rawcandle/data/osakedata.csv"
    
    # Tarkista että CSV-tiedosto on olemassa
    if not os.path.exists(csv_file_path):
        return False, f"CSV-tiedostoa ei löytynyt: {csv_file_path}", 0
    
    saved_count = 0
    failed_tickers = []
    found_tickers = set()
    
    db_path = get_db_path('osakedata')
    
    try:
        with sqlite3.connect(db_path) as conn:
            cursor = conn.cursor()
            
            # Varmista että taulu on olemassa
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS osakedata (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    osake TEXT,
                    pvm DATE,
                    open REAL,
                    high REAL,
                    low REAL,
                    close REAL,
                    volume INTEGER,
                    UNIQUE(osake, pvm)
                )
            """)
            
            # Varmista UNIQUE-indeksi duplikaattien estämiseksi
            cursor.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_osake_pvm ON osakedata(osake, pvm)")
            
            # Lue CSV-tiedosto
            with open(csv_file_path, 'r', encoding='utf-8') as csvfile:
                # CSV ei sisällä otsikoita, joten määritellään sarakkeet manuaalisesti
                # Oletettu rakenne: ticker,date,open,high,low,close,volume,date2,open2,...
                # Käsitellään vain ensimmäiset 7 saraketta per ticker
                
                content = csvfile.read().strip()
                # Jaa rivit ja käsittele data
                lines = content.split('\n')
                
                for line in lines:
                    if not line.strip():
                        continue
                    
                    # Jaa pilkuilla
                    fields = line.split(',')
                    
                    if len(fields) < 7:  # Liian vähän kenttiä
                        continue
                    
                    # Ensimmäinen kenttä on ticker
                    ticker = fields[0].strip()
                    
                    # Massa-ajossa käsitellään kaikki tickerit, muuten vain pyydetyt
                    if not mass_import and clean_tickers and ticker not in clean_tickers:
                        continue
                    
                    found_tickers.add(ticker)
                    
                    # Loput kentät ovat 6-kenttien ryhmiä: date, open, high, low, close, volume
                    for i in range(1, len(fields), 6):
                        if i + 5 >= len(fields):  # Ei tarpeeksi kenttiä tälle ryhmälle
                            break
                        
                        try:
                            date_str = fields[i].strip()
                            open_price = float(fields[i + 1])
                            high_price = float(fields[i + 2])
                            low_price = float(fields[i + 3])
                            close_price = float(fields[i + 4])
                            volume = int(float(fields[i + 5]))  # Muunna float -> int
                            
                            # Muunna päivämäärä oikeaan muotoon
                            try:
                                date_obj = datetime.strptime(date_str, '%Y-%m-%d')
                                formatted_date = date_obj.strftime('%Y-%m-%d')
                            except ValueError:
                                continue  # Ohita virheelliset päivämäärät
                            
                            # Tarkista onko päivämäärä jo olemassa
                            cursor.execute(
                                "SELECT COUNT(*) FROM osakedata WHERE osake = ? AND pvm = ?",
                                (ticker, formatted_date)
                            )
                            
                            if cursor.fetchone()[0] == 0:  # Ei ole olemassa
                                cursor.execute("""
                                    INSERT INTO osakedata (osake, pvm, open, high, low, close, volume)
                                    VALUES (?, ?, ?, ?, ?, ?, ?)
                                """, (
                                    ticker,
                                    formatted_date,
                                    open_price,
                                    high_price,
                                    low_price,
                                    close_price,
                                    volume
                                ))
                                saved_count += 1
                                
                        except (ValueError, IndexError) as e:
                            continue  # Ohita virheelliset rivit
            
            conn.commit()
            
            # Tarkista mitkä tickerit löytyivät (vain jos ei massa-ajo)
            if not mass_import and clean_tickers:
                not_found_tickers = [t for t in clean_tickers if t not in found_tickers]
                if not_found_tickers:
                    failed_tickers.extend([f"{ticker} (ei löytynyt CSV:stä)" for ticker in not_found_tickers])
            
            # Muodosta vastausviesti
            if saved_count > 0:
                if mass_import:
                    success_msg = f"MASSA-AJO: Tallennettu {saved_count} riviä CSV:stä ({len(found_tickers)} osaketta)"
                else:
                    success_msg = f"Tallennettu {saved_count} riviä CSV:stä"
                
                if failed_tickers:
                    return True, f"{success_msg}. Epäonnistui: {', '.join(failed_tickers)}", saved_count
                else:
                    return True, success_msg, saved_count
            else:
                if mass_import:
                    return False, "MASSA-AJO: Ei tallennettu yhtään uutta riviä CSV:stä (kaikki jo olemassa)", 0
                elif failed_tickers:
                    return False, f"Ei tallennettu yhtään riviä CSV:stä. Epäonnistui: {', '.join(failed_tickers)}", 0
                else:
                    return False, "Ei tallennettu yhtään riviä CSV:stä (kaikki jo olemassa)", 0
                    
    except Exception as e:
        return False, f"Virhe CSV-lukemisessa: {str(e)}", 0


@app.route('/')
def index():
    """Pääsivu."""
    # Hae oletus-tietokannan symbolit
    db_type = 'osakedata'
    available_symbols = get_available_symbols(db_type)
    return render_template('index.html', 
                         available_symbols=available_symbols,
                         current_db=db_type,
                         db_label=get_db_label(db_type))

@app.route('/search', methods=['POST'])
def search_stocks():
    """Hae data annetuille hakutermeille valitusta tietokannasta."""
    ticker_input = request.form.get('tickers', '').strip()
    db_type = request.form.get('db_type', 'osakedata')
    
    if not ticker_input:
        return render_template('index.html', 
                             error="Anna vähintään yksi hakutermi (symboli tai sen alku)",
                             available_symbols=get_available_symbols(db_type),
                             current_db=db_type,
                             db_label=get_db_label(db_type))
    
    # Jaa hakutermit pilkulla ja poista tyhjät
    search_terms = [s.strip().upper() for s in ticker_input.split(',') if s.strip()]
    
    if not search_terms:
        return render_template('index.html', 
                             error="Anna vähintään yksi kelvollinen hakutermi",
                             available_symbols=get_available_symbols(db_type),
                             current_db=db_type,
                             db_label=get_db_label(db_type))
    
    # Hae data tietokannasta (tukee osittaista hakua)
    df, error, found_symbols = get_stock_data(search_terms, db_type)
    
    if error:
        return render_template('index.html', 
                             error=error,
                             available_symbols=get_available_symbols(db_type),
                             current_db=db_type,
                             db_label=get_db_label(db_type))
    
    # Muuta DataFrame HTML-taulukoksi
    if not df.empty:
        # Muotoile data tietokantatyypin mukaan
        if db_type == 'osakedata':
            # Muotoile osakedata numerot
            for col in ['open', 'high', 'low', 'close']:
                if col in df.columns:
                    df[col] = df[col].round(2)
            if 'volume' in df.columns:
                df['volume'] = df['volume'].apply(lambda x: f"{x:,}")
        
        # Luo HTML-taulukko
        table_html = df.to_html(classes='table table-striped table-hover', 
                               index=False, escape=False, table_id='stockTable')
        
        return render_template('index.html', 
                             table_html=table_html,
                             searched_terms=search_terms,
                             found_symbols=found_symbols,
                             record_count=len(df),
                             available_symbols=get_available_symbols(db_type),
                             current_db=db_type,
                             db_label=get_db_label(db_type))
    else:
        return render_template('index.html', 
                             error="Ei löytynyt tietoja annetuille hakutermeille",
                             available_symbols=get_available_symbols(db_type),
                             current_db=db_type,
                             db_label=get_db_label(db_type))

@app.route('/delete', methods=['POST'])
def delete_stocks():
    """Poista data annetuille symboleille käyttäjän vahvistuksen jälkeen."""
    ticker_input = request.form.get('delete_tickers', '').strip()
    db_type = request.form.get('db_type', 'osakedata')
    confirm = request.form.get('confirm_delete', '').strip().lower()
    
    if not ticker_input:
        return render_template('index.html', 
                             error="Anna symbolit joiden data haluat poistaa",
                             available_symbols=get_available_symbols(db_type),
                             current_db=db_type,
                             db_label=get_db_label(db_type))
    
    # Jaa symbolit pilkulla ja poista tyhjät
    symbols_to_delete = [s.strip().upper() for s in ticker_input.split(',') if s.strip()]
    
    if not symbols_to_delete:
        return render_template('index.html', 
                             error="Anna vähintään yksi kelvollinen symboli poistettavaksi",
                             available_symbols=get_available_symbols(db_type),
                             current_db=db_type,
                             db_label=get_db_label(db_type))
    
    # Tarkista varmistus
    if confirm != 'kyllä' and confirm != 'kylla' and confirm != 'yes':
        return render_template('index.html', 
                             error="Poistotoiminto peruutettu. Varmistus puuttui tai oli väärä.",
                             available_symbols=get_available_symbols(db_type),
                             current_db=db_type,
                             db_label=get_db_label(db_type))
    
    # Suorita poisto
    success, message, deleted_count = delete_stock_data(symbols_to_delete, db_type)
    
    if success:
        return render_template('index.html', 
                             success=message,
                             available_symbols=get_available_symbols(db_type),
                             current_db=db_type,
                             db_label=get_db_label(db_type))
    else:
        return render_template('index.html', 
                             error=message,
                             available_symbols=get_available_symbols(db_type),
                             current_db=db_type,
                             db_label=get_db_label(db_type))


@app.route('/fetch_yfinance', methods=['POST'])
def fetch_yfinance_route():
    """Hae OHLCV-data Yahoo Financesta."""
    ticker_input = request.form.get('tickers', '').strip()
    
    if not ticker_input:
        return render_template('index.html', 
                             error="Anna vähintään yksi ticker-symboli",
                             available_symbols=get_available_symbols('osakedata'),
                             current_db='osakedata',
                             db_label=get_db_label('osakedata'))
    
    # Jaa tickerit pilkulla
    tickers = [t.strip().upper() for t in ticker_input.split(',') if t.strip()]
    
    # Hae data YFinancesta
    success, message, count = fetch_yfinance_data(tickers)
    
    if success:
        return render_template('index.html', 
                             success=message,
                             available_symbols=get_available_symbols('osakedata'),
                             current_db='osakedata',
                             db_label=get_db_label('osakedata'))
    else:
        return render_template('index.html', 
                             error=message,
                             available_symbols=get_available_symbols('osakedata'),
                             current_db='osakedata',
                             db_label=get_db_label('osakedata'))


@app.route('/fetch_tickers', methods=['POST'])
def fetch_tickers_route():
    """Hae OHLCV-data Yahoo Financesta tickers.txt tiedostosta."""
    
    # Tarkista että tiedosto on olemassa
    import os
    tickers_file = "/home/kalle/projects/rawcandle/data/tickers.txt"
    
    if not os.path.exists(tickers_file):
        return jsonify({
            'success': False,
            'message': f"Tickers-tiedostoa ei löytynyt: {tickers_file}"
        })
    
    # Lue tiedosto ja laske tickerien määrä
    try:
        with open(tickers_file, 'r', encoding='utf-8') as f:
            ticker_count = len([line.strip() for line in f if line.strip()])
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f"Virhe tickers-tiedoston lukemisessa: {str(e)}"
        })
    
    if ticker_count == 0:
        return jsonify({
            'success': False,
            'message': "Tickers-tiedosto on tyhjä"
        })
    
    # Hae data tiedostosta
    success, message, stats = fetch_tickers_from_file()
    
    if success:
        return jsonify({
            'success': True,
            'message': message,
            'processed': stats.get('processed', 0),
            'success_count': stats.get('success_count', 0),
            'error_count': stats.get('error_count', 0)
        })
    else:
        return jsonify({
            'success': False,
            'message': message
        })


@app.route('/fetch_csv', methods=['POST'])
def fetch_csv_route():
    """
    Hae OHLCV-data CSV-tiedostosta.
    
    MASSA-AJO: Jos ticker-kenttä on tyhjä, ladataan KAIKKI CSV:ssä olevat osakkeet.
    Jos tickereitä on annettu, ladataan vain ne.
    """
    ticker_input = request.form.get('tickers', '').strip()
    
    if not ticker_input:
        # MASSA-AJO: Tyhjä syöte = lataa kaikki CSV:ssä olevat osakkeet
        success, message, count = fetch_csv_data(None)
    else:
        # Jaa tickerit pilkulla ja hae vain ne
        tickers = [t.strip().upper() for t in ticker_input.split(',') if t.strip()]
        success, message, count = fetch_csv_data(tickers)
    # Renderöi tulos
    if success:
        return render_template('index.html', 
                             success=message,
                             available_symbols=get_available_symbols('osakedata'),
                             current_db='osakedata',
                             db_label=get_db_label('osakedata'))
    else:
        return render_template('index.html', 
                             error=message,
                             available_symbols=get_available_symbols('osakedata'),
                             current_db='osakedata',
                             db_label=get_db_label('osakedata'))


@app.route('/clear_database', methods=['POST'])
def clear_database_route():
    """Tyhjennä valittu tietokanta - VAARALLINEN TOIMINTO!"""
    db_type = request.form.get('db_type', 'osakedata')
    confirm = request.form.get('confirm_clear', '').strip().lower()
    double_confirm = request.form.get('double_confirm', '').strip()
    
    # Tarkista vahvistukset
    if confirm not in ['kyllä', 'kylla', 'yes']:
        return render_template('index.html', 
                             error="Tietokannan tyhjentäminen vaatii vahvistuksen",
                             available_symbols=get_available_symbols(db_type),
                             current_db=db_type,
                             db_label=get_db_label(db_type))
    
    # Tuplavirus - käyttäjän täytyy kirjoittaa "TYHJENNÄ" 
    if double_confirm != 'TYHJENNÄ':
        return render_template('index.html', 
                             error="Turvallisuussyistä sinun täytyy kirjoittaa 'TYHJENNÄ' vahvistaaksesi toiminnon",
                             available_symbols=get_available_symbols(db_type),
                             current_db=db_type,
                             db_label=get_db_label(db_type))
    
    # Suorita tietokannan tyhjentäminen
    success, message, deleted_count = clear_database(db_type)
    
    if success:
        return render_template('index.html', 
                             success=message,
                             available_symbols=get_available_symbols(db_type),
                             current_db=db_type,
                             db_label=get_db_label(db_type))
    else:
        return render_template('index.html', 
                             error=message,
                             available_symbols=get_available_symbols(db_type),
                             current_db=db_type,
                             db_label=get_db_label(db_type))

@app.route('/api/symbols')
def api_symbols():
    """API-endpoint saatavilla olevien symbolien hakemiseen - optimoitu suurille tietomäärille."""
    db_type = request.args.get('db_type', 'osakedata')
    page = request.args.get('page', type=int)
    limit = request.args.get('limit', type=int)
    search = request.args.get('search', '').strip()
    
    try:
        symbols = get_available_symbols(db_type)
        
        # Suodata hakutermillä jos annettu
        if search:
            symbols = [s for s in symbols if search.lower() in s.lower()]
        
        total_count = len(symbols)
        
        # Pagination jos pyydetty
        if page is not None and limit is not None:
            start = (page - 1) * limit
            end = start + limit
            symbols = symbols[start:end]
            
            return jsonify({
                'symbols': symbols,
                'total': total_count,
                'page': page,
                'limit': limit,
                'total_pages': (total_count + limit - 1) // limit
            })
        
        # Palauta kaikki symbolit jos ei paginationia
        return jsonify(symbols)
        
    except Exception as e:
        app.logger.error(f"Error in api_symbols: {e}")
        return jsonify({'error': 'Virhe symbolien lataamisessa'}), 500

@app.route('/api/symbols/search')
def api_symbols_search():
    """Nopea symbolien haku autocomplete-toiminnallisuudelle."""
    db_type = request.args.get('db_type', 'osakedata')
    query = request.args.get('q', '').strip().upper()
    limit = request.args.get('limit', 10, type=int)
    
    if not query or len(query) < 1:
        return jsonify([])
    
    try:
        symbols = get_available_symbols(db_type)
        
        # Etsi symbolit jotka alkavat hakutermillä (nopein)
        matches = [s for s in symbols if s.startswith(query)]
        
        # Jos ei löydy, etsi symbolit jotka sisältävät hakutermin
        if not matches:
            matches = [s for s in symbols if query in s]
        
        # Rajoita tulokset
        matches = matches[:limit]
        
        return jsonify(matches)
        
    except Exception as e:
        app.logger.error(f"Error in api_symbols_search: {e}")
        return jsonify({'error': 'Virhe symbolien haussa'}), 500

if __name__ == "__main__":
    app.run(debug=True, host='0.0.0.0', port=5001)