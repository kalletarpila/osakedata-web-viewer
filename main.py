#!/usr/bin/env python3
"""
Stock Data Web Viewer
A Flask web application for viewing stock data from SQLite database.
"""

from flask import Flask, render_template, request, jsonify
import sqlite3
import pandas as pd
import os

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
            # Analysis-tietokanta: ticker, date, pattern
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
            symbol_col = 'ticker' if 'ticker' in df.columns else 'osake'
            found_symbols = df[symbol_col].unique().tolist() if not df.empty else []
        else:
            symbol_col = 'osake' if 'osake' in df.columns else 'ticker'
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
                    ORDER BY ticker COLLATE NOCASE
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