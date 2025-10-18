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

# Tietokannan sijainti
DB_PATH = "/home/kalle/projects/rawcandle/data/osakedata.db"

def get_stock_data(search_terms):
    """
    Hae osakedata tietokannasta. Tukee sekä tarkkaa hakua että osittaista hakua.
    
    Args:
        search_terms (list): Lista hakutermeistä (voivat olla tarkkoja symboleja tai alkuja)
    
    Returns:
        pandas.DataFrame: Osakedata tietokannasta
        str: Virheviesti tai None
        list: Löytyneet symbolit
    """
    if not os.path.exists(DB_PATH):
        return pd.DataFrame(), f"Tietokanta ei löydy: {DB_PATH}", []
    
    try:
        # Rakenna SQL-kysely, joka tukee sekä tarkkaa että osittaista hakua
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
        
        with sqlite3.connect(DB_PATH) as conn:
            df = pd.read_sql_query(query, conn, params=params)
        
        # Hae löytyneet uniikit symbolit
        found_symbols = df['osake'].unique().tolist() if not df.empty else []
        
        if df.empty:
            return df, f"Ei löytynyt tietoja hakutermeille: {', '.join(search_terms)}", []
        
        return df, None, found_symbols
        
    except Exception as e:
        return pd.DataFrame(), f"Virhe tietokannasta hakiessa: {str(e)}", []

def get_available_symbols():
    """Hae kaikki saatavilla olevat osake-symbolit tietokannasta."""
    if not os.path.exists(DB_PATH):
        return []
    
    try:
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT DISTINCT osake FROM osakedata ORDER BY osake")
            symbols = [row[0] for row in cursor.fetchall()]
        return symbols
    except Exception as e:
        print(f"Virhe symbolien hakemisessa: {e}")
        return []

def delete_stock_data(symbols_to_delete):
    """
    Poista osakedata tietokannasta annetuille symboleille.
    
    Args:
        symbols_to_delete (list): Lista poistettavista symboleista
    
    Returns:
        tuple: (onnistui (bool), viesti (str), poistettujen_rivien_määrä (int))
    """
    if not os.path.exists(DB_PATH):
        return False, f"Tietokanta ei löydy: {DB_PATH}", 0
    
    try:
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            
            # Laske ensin montako riviä poistetaan
            placeholders = ','.join('?' * len(symbols_to_delete))
            count_query = f"SELECT COUNT(*) FROM osakedata WHERE osake IN ({placeholders})"
            cursor.execute(count_query, symbols_to_delete)
            rows_to_delete = cursor.fetchone()[0]
            
            if rows_to_delete == 0:
                return False, f"Ei löytynyt poistettavia rivejä symboleille: {', '.join(symbols_to_delete)}", 0
            
            # Poista rivit
            delete_query = f"DELETE FROM osakedata WHERE osake IN ({placeholders})"
            cursor.execute(delete_query, symbols_to_delete)
            
            conn.commit()
            
            return True, f"Poistettu {rows_to_delete} riviä symboleille: {', '.join(symbols_to_delete)}", rows_to_delete
            
    except Exception as e:
        return False, f"Virhe tietojen poistossa: {str(e)}", 0

@app.route('/')
def index():
    """Pääsivu."""
    available_symbols = get_available_symbols()
    return render_template('index.html', available_symbols=available_symbols)

@app.route('/search', methods=['POST'])
def search_stocks():
    """Hae osakedata annetuille hakutermeille. Tukee sekä tarkkaa että osittaista hakua."""
    ticker_input = request.form.get('tickers', '').strip()
    
    if not ticker_input:
        return render_template('index.html', 
                             error="Anna vähintään yksi hakutermi (osake-symboli tai sen alku)",
                             available_symbols=get_available_symbols())
    
    # Jaa hakutermit pilkulla ja poista tyhjät
    search_terms = [s.strip().upper() for s in ticker_input.split(',') if s.strip()]
    
    if not search_terms:
        return render_template('index.html', 
                             error="Anna vähintään yksi kelvollinen hakutermi",
                             available_symbols=get_available_symbols())
    
    # Hae data tietokannasta (tukee osittaista hakua)
    df, error, found_symbols = get_stock_data(search_terms)
    
    if error:
        return render_template('index.html', 
                             error=error,
                             available_symbols=get_available_symbols())
    
    # Muuta DataFrame HTML-taulukoksi
    if not df.empty:
        # Muotoile päivämäärät ja numerot (pvm-sarake on jo teksti-muodossa)
        # df['pvm'] on jo oikeassa muodossa, ei tarvitse muuntaa
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
                             available_symbols=get_available_symbols())
    else:
        return render_template('index.html', 
                             error="Ei löytynyt tietoja annetuille hakutermeille",
                             available_symbols=get_available_symbols())

@app.route('/delete', methods=['POST'])
def delete_stocks():
    """Poista osakedata annetuille symboleille käyttäjän vahvistuksen jälkeen."""
    ticker_input = request.form.get('delete_tickers', '').strip()
    confirm = request.form.get('confirm_delete', '').strip().lower()
    
    if not ticker_input:
        return render_template('index.html', 
                             error="Anna symbolit joiden data haluat poistaa",
                             available_symbols=get_available_symbols())
    
    # Jaa symbolit pilkulla ja poista tyhjät
    symbols_to_delete = [s.strip().upper() for s in ticker_input.split(',') if s.strip()]
    
    if not symbols_to_delete:
        return render_template('index.html', 
                             error="Anna vähintään yksi kelvollinen symboli poistettavaksi",
                             available_symbols=get_available_symbols())
    
    # Tarkista varmistus
    if confirm != 'kyllä' and confirm != 'kylla' and confirm != 'yes':
        return render_template('index.html', 
                             error="Poistotoiminto peruutettu. Varmistus puuttui tai oli väärä.",
                             available_symbols=get_available_symbols())
    
    # Suorita poisto
    success, message, deleted_count = delete_stock_data(symbols_to_delete)
    
    if success:
        return render_template('index.html', 
                             success=message,
                             available_symbols=get_available_symbols())
    else:
        return render_template('index.html', 
                             error=message,
                             available_symbols=get_available_symbols())

@app.route('/api/symbols')
def api_symbols():
    """API-endpoint saatavilla olevien symbolien hakemiseen."""
    symbols = get_available_symbols()
    return jsonify(symbols)

if __name__ == "__main__":
    app.run(debug=True, host='0.0.0.0', port=5000)