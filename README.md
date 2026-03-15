# FIS-Alpine-Athlete-Analysis

Robustere Streamlit-Version für GitHub und Streamlit Community Cloud.

## Was in v2 verbessert wurde
- Direkte Suche über die FIS-Biography-Suche
- Suche per **Name** oder **FIS-Code**
- Ergebnisliste mit Auswahl
- Robusteres Matching
- Fallback-Suche, falls die direkte Ergebnisliste leer bleibt

## Dateien
- `streamlit_app.py` – Streamlit-App
- `requirements.txt` – Abhängigkeiten
- `README.md` – Projektbeschreibung
- `.gitignore` – sinnvolle Git-Regeln

## Lokal starten
```bash
pip install -r requirements.txt
streamlit run streamlit_app.py
```

## Deployment auf Streamlit Community Cloud
1. Repository auf GitHub anlegen
2. Alle Dateien hochladen
3. In Streamlit Community Cloud das Repository auswählen
4. `streamlit_app.py` als Main file setzen
5. Deploy starten

## Hinweis
Die App ist bewusst auf Streamlit + GitHub optimiert und benötigt keine PyQt-Desktop-Komponenten.
