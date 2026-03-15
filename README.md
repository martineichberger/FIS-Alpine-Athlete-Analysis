# FIS-Alpine-Athlete-Analysis

Version **v5.8** überarbeitet die Ergebnisanzeige deutlich und macht den Reiter Ergebnisse klarer und auswertbarer.

- `streamlit_app.py`
- `requirements.txt`
- `README.md`

## Neu in v5.8

- Athletensuche funktioniert wieder stabil
- FIS-Code wird in Trefferliste und Detailansicht zuverlässig angezeigt
- lokale Cache-Lösung für
  - Athletensuche
  - FIS-Profile
  - Ergebnisseiten
- schnelleres erneutes Laden bereits abgefragter Athleten
- Button zum Leeren des lokalen Caches direkt in der App

## Cache-Verhalten

Beim Start legt die App automatisch einen lokalen Ordner an:

```bash
.cache/fis_app
```

Dort werden Suchergebnisse und FIS-Daten zeitlich begrenzt zwischengespeichert. Dadurch werden wiederholte Anfragen schneller und die FIS-Seiten müssen seltener neu geladen werden.

## Lokal starten

```bash
pip install -r requirements.txt
streamlit run streamlit_app.py
```

## Für GitHub / Streamlit Cloud

Diese Struktur ist direkt für ein kleines GitHub-Repository geeignet. Als Startdatei verwendest du:

```bash
streamlit_app.py
```


Neu:
- Ergebnisanzeige mit klareren Filtern für Saison, Disziplin, Kategorie und Status
- zusätzliche Status-Spalte je Rennen
- Tabs für Übersicht, Ergebnisliste und Disziplinenvergleich
- bessere KPI-Anzeige für Gewertet, Podien, DNF sowie DSQ/DNS
- Saisonüberblick im Reiter Athletendaten bleibt erhalten
