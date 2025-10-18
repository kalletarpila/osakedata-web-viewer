#!/bin/bash

# Pysäytä vanhat Flask-prosessit
echo "Pysäytetään vanhat Flask-prosessit..."
pkill -f "python main.py" 2>/dev/null || echo "Ei vanhoja prosesseja löytynyt"

# Odota hetki että prosessit ehtivät sulkeutua
sleep 2

# Tarkista jos portti 5000 on vielä käytössä ja vapauta se
if lsof -ti:5000 >/dev/null 2>&1; then
    echo "Portti 5000 on vielä käytössä, tapetaan prosessi..."
    kill -9 $(lsof -ti:5000) 2>/dev/null || echo "Portin vapauttaminen epäonnistui"
    sleep 1
fi

# Käynnistä Flask web-sovellus
echo "Käynnistetään Osakedata Web Viewer..."
echo "Sovellus on saatavilla osoitteessa: http://localhost:5000"
echo "Pysäytä painamalla Ctrl+C"
echo ""

cd /home/kalle/projects/test
/home/kalle/projects/test/.venv/bin/python main.py