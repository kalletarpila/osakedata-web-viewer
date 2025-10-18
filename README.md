# Stock Data Web Viewer

Flask web application for viewing stock data from multiple SQLite databases.

## Features

- **Multi-Database Support**: Switch between different data sources
  - **Osakedata**: OHLCV stock market data
  - **Analysis**: Candlestick pattern analysis results
- **Web Interface**: Clean, responsive web UI using Bootstrap
- **Partial Search**: Search by full ticker symbol or partial matches (e.g., "AA" finds all symbols starting with "AA")
- **Data Visualization**: Display data in sortable HTML tables
- **Click Navigation**: Click on available symbol badges to quickly search
- **Delete Operations**: Remove data with confirmation prompts
- **Database Integration**: Direct SQLite database queries with pandas
- **Dynamic Symbol Loading**: Automatically updates available symbols when switching databases

## Databases

The application supports two databases:

### 1. Osakedata (OHLCV Stock Data)
- **Path**: `/home/kalle/projects/rawcandle/data/osakedata.db`
- **Table**: `osakedata`
- **Columns**: `id, osake, pvm, open, high, low, close, volume`

### 2. Analysis (Candlestick Pattern Analysis)
- **Path**: `/home/kalle/projects/rawcandle/analysis/analysis.db`
- **Table**: `analysis_findings`
- **Columns**: `id, ticker, date, pattern`

## Requirements

- Python 3.7+
- Flask 2.3.0+
- pandas 2.0.0+
- SQLite3 (built-in)

## Installation

1. Clone or download the project
2. Create virtual environment and install dependencies:
   ```bash
   python -m venv .venv
   source .venv/bin/activate  # Linux/Mac
   pip install -r requirements.txt
   ```

## Usage

### Starting the Web Application

```bash
# Option 1: Using startup script (recommended)
./start_server.sh

# Option 2: Direct Python command
python main.py
```

The application starts at: `http://localhost:5000`

### Using the Application

1. **Select Database**: Choose between "Osakedata (OHLCV)" or "Kynttiläkuvioanalyysi" from the dropdown
2. **Search Data**: Enter symbol(s) or partial symbols (e.g., "AAPL" or just "AA")
3. **Quick Access**: Click on available symbol badges to quickly search
4. **Delete Data**: Use the delete button with confirmation for data removal
5. **Navigation**: Smooth scrolling to results table

### Palvelimen pysäytys

```bash
# Pysäytä palvelin ja vapauta portti
./stop_server.sh

# Tai käytä Ctrl+C jos ajat start_server.sh:lla
```

### Tietokannan sijainti

Sovellus hakee dataa tietokannasta: `/home/kalle/projects/rawcandle/data/osakedata.db`

### Käyttöliittymä

1. **Yhteinen hakukenttä**: Sama kenttä hakuun ja poistoon
2. **Hae data -nappi**: Hae ja näytä osakedata
3. **Poista data -nappi**: Poista valittujen symbolien tiedot (vaatii checkbox-varmistuksen)
4. **Osittainen haku**: Anna symbolin alku (esim. "AA") niin löytyvät kaikki sillä alkavat symbolit
5. **Klikkaa symboleja**: Voit klikata saatavilla olevia symboleja täyttääksesi hakukentän
6. **Automaattinen scrollaus**: Sivu skrollaa automaattisesti tuloksiin
7. **Kopioi-nappi**: Kopioi löytyneet symbolit takaisin hakukenttään

### Esimerkkihaut

**Tarkka haku:**
- Yksi osake: `AAPL`
- Useita osakkeita: `AAPL, GOOGL, MSFT`

**Osittainen haku (symbolin alku):**
- Kaikki AA-alkuiset: `AA`
- Useita alkuja: `AA, GOO, MS`
- Sekaisin: `AAPL, GOO, TSLA`

**Huom:** Isot/pienet kirjaimet muunnetaan automaattisesti isoiksi

### Datan poistaminen

**Varoitus!** Poistotoiminto poistaa pysyvästi kaikki valitun symbolin tiedot.

1. **Anna symbolit**: Kirjoita hakukenttään poistettavat symbolit
2. **Klikkaa "Poista data"**: Varmistusruutu ilmestyy
3. **Rastita varmistus**: "Vahvistan että haluan poistaa..."
4. **Vahvista**: Selain kysyy vielä lopullisen varmistuksen
5. **Poisto**: Kaikki symbolien tiedot poistetaan pysyvästi

**Helppokäyttöisyys:**
- Hae ensin symbolit → Klikkaa "📋 Kopioi löytyneet symbolit" → Klikkaa "Poista data"
- Sivu skrollaa automaattisesti varmistusruutuun
- Pelkkä checkbox-rastitus riittää varmistukseksi

## Tietokannan rakenne

Sovellus lukee `osakedata`-taulua, jossa on seuraavat sarakkeet:
- `id` - Pääavain (INTEGER PRIMARY KEY AUTOINCREMENT)
- `osake` - Osake-symboli (TEXT)
- `pvm` - Kaupankäyntipäivä (TEXT)
- `open`, `high`, `low`, `close` - Hintadata (REAL)
- `volume` - Kaupankäyntivolyymi (INTEGER)

**Huom:** Sovellus näyttää kaikki tietokantarivit, myös mahdolliset duplikaatit. Tämä auttaa tietojen laadun tarkkailussa ja virheiden havaitsemisessa.

## API-päätepisteet

- `GET /` - Pääsivu
- `POST /search` - Osakkeiden haku
- `GET /api/symbols` - JSON-lista saatavilla olevista symboleista

## Kehitys

Sovellus käyttää Flask debug-tilaa kehityksessä. Tuotannossa aseta `debug=False`.

### Portin ja hostin muutos

```python
app.run(debug=False, host='127.0.0.1', port=8080)
```

## Vianmääritys

- **Tietokanta ei löydy**: Tarkista että `osakedata.db` on oikeassa hakemistossa
- **Ei dataa**: Varmista että tietokannassa on `stock_data`-taulu datalla
- **Portti varattu**: Muuta porttia `app.run()` -kutsulla

## Lisenssi

Tämä projekti on avoimen lähdekoodin MIT-lisenssillä.