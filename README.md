# Osakedata Web Viewer

Flask-pohjainen web-sovellus osakedata-tietokannan tarkasteluun. Sovellus lukee osakedata.db-tietokantaa ja näyttää osakkeiden tiedot selaimessa.

## Ominaisuudet

- Web-käyttöliittymä osakedata-tietokannan tarkasteluun
- Haku yhdellä tai useammalla osake-symbolilla
- Responsiivinen Bootstrap-käyttöliittymä
- Saatavilla olevien symbolien listaus
- Datan näyttö järjestetyssä taulukossa

## Vaatimukset

- Python 3.7+
- Flask
- pandas
- SQLite3 (sisäänrakennettu)

## Asennus

1. Kloonaa tai lataa projekti
2. Asenna riippuvuudet:
   ```bash
   pip install -r requirements.txt
   ```

## Käyttö

### Web-sovelluksen käynnistys

```bash
# Vaihtoehto 1: Käynnistysskriptillä (suositeltu)
./start_server.sh

# Vaihtoehto 2: Suoraan Python-komennolla
python main.py
```

Sovellus käynnistyy osoitteeseen: `http://localhost:5000`

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