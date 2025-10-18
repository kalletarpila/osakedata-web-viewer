#!/bin/bash

# Pysäytä Flask web-sovellus
echo "Pysäytetään Osakedata Web Viewer..."

# Pysäytä Flask-prosessit
pkill -f "python main.py" 2>/dev/null && echo "Flask-prosessit pysäytetty" || echo "Ei Flask-prosesseja löytynyt"

# Tarkista ja vapauta portti 5000 jos tarpeen
if lsof -ti:5000 >/dev/null 2>&1; then
    echo "Vapautetaan portti 5000..."
    kill -9 $(lsof -ti:5000) 2>/dev/null && echo "Portti 5000 vapautettu" || echo "Portin vapauttaminen epäonnistui"
else
    echo "Portti 5000 on jo vapaa"
fi
# Tarkista ja vapauta portti 5000 jos tarpeen
if lsof -ti:5001 >/dev/null 2>&1; then
    echo "Vapautetaan portti 5001..."
    kill -9 $(lsof -ti:5001) 2>/dev/null && echo "Portti 5001 vapautettu" || echo "Portin vapauttaminen epäonnistui"
else
    echo "Portti 5000 on jo vapaa"
fi


echo "Palvelin pysäytetty."