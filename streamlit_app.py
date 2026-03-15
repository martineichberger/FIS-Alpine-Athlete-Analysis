import html
import re
from urllib.parse import urlencode, quote_plus

import requests
import streamlit as st
import pandas as pd

APP_NAME = "FIS-Alpine-Athlete-Analysis"
APP_VERSION = "v4.0-streamlit"
USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/122.0.0.0 Safari/537.36"
)
TIMEOUT = 25
FIS_SEARCH_URL = "https://www.fis-ski.com/DB/general/biographies.html"
FIS_PROFILE_PREFIX = "https://www.fis-ski.com"
DUCKDUCKGO_HTML = "https://html.duckduckgo.com/html/"

st.set_page_config(
    page_title=APP_NAME,
    page_icon="⛷️",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown(
    """
    <style>
        :root {
            --navy: #102649;
            --navy-2: #173865;
            --line: #d8e1ef;
            --text: #102038;
            --muted: #64748b;
            --white: #ffffff;
            --card: #ffffff;
            --accent: #1f6feb;
        }

        .stApp {
            background: #ffffff;
        }

        [data-testid="stSidebar"] {
            background: #ffffff;
            border-right: 1px solid var(--line);
        }

        .header-shell {
            background: var(--navy);
            margin: -1rem -1rem 1rem -1rem;
            padding: 0.8rem 1.2rem;
            border-bottom: 1px solid #274a7f;
        }

        .header-title {
            color: #ffffff;
            font-size: 1.45rem;
            font-weight: 800;
            text-align: center;
            line-height: 1.2;
            margin-top: 0.2rem;
        }

        .header-version {
            color: #cddaf0;
            text-align: right;
            font-size: 0.9rem;
            padding-top: 0.35rem;
        }

        .content-title {
            color: var(--text);
            font-size: 1.15rem;
            font-weight: 800;
            margin-bottom: 0.75rem;
        }

        .hero-card {
            background: var(--card);
            border: 1px solid var(--line);
            border-radius: 18px;
            padding: 1rem 1.1rem;
            margin-bottom: 1rem;
            box-shadow: 0 2px 14px rgba(16, 32, 56, 0.05);
        }

        .hero-name {
            color: var(--text);
            font-size: 1.65rem;
            font-weight: 900;
            line-height: 1.1;
        }

        .hero-meta {
            color: var(--muted);
            font-size: 0.95rem;
            margin-top: 0.35rem;
        }

        .metric-card {
            background: #ffffff;
            border: 1px solid var(--line);
            border-radius: 16px;
            padding: 0.9rem 1rem;
            margin-bottom: 0.8rem;
            min-height: 92px;
            box-shadow: 0 2px 10px rgba(16, 32, 56, 0.04);
        }

        .metric-label {
            color: var(--muted);
            font-size: 0.76rem;
            text-transform: uppercase;
            letter-spacing: 0.4px;
            margin-bottom: 0.25rem;
        }

        .metric-value {
            color: var(--text);
            font-size: 1rem;
            font-weight: 800;
            line-height: 1.25;
            word-break: break-word;
        }

        .kpi {
            background: #f7f9fc;
            border: 1px solid var(--line);
            border-radius: 16px;
            padding: 0.9rem 1rem;
            margin-bottom: 0.8rem;
        }

        .kpi-label {
            color: var(--muted);
            font-size: 0.76rem;
            text-transform: uppercase;
            letter-spacing: 0.4px;
        }

        .kpi-value {
            color: var(--text);
            font-size: 1.3rem;
            font-weight: 900;
            margin-top: 0.2rem;
        }

        .panel-note {
            background: #f8fbff;
            border: 1px solid var(--line);
            color: var(--muted);
            border-radius: 14px;
            padding: 0.8rem 0.95rem;
            margin-bottom: 1rem;
        }

        .mini-card {
            background: #ffffff;
            border: 1px solid var(--line);
            border-radius: 16px;
            padding: 0.9rem;
            margin-bottom: 0.8rem;
        }

        .footer-note {
            color: var(--muted);
            font-size: 0.86rem;
            margin-top: 1rem;
        }

        .nav-caption {
            color: var(--muted);
            font-size: 0.85rem;
            margin-top: 0.25rem;
        }

        div[data-testid="stTextInput"] input {
            border-radius: 12px !important;
            border: 1px solid #c9d5e7 !important;
        }

        div.stButton > button {
            border-radius: 12px !important;
            font-weight: 700 !important;
        }

        div[data-testid="stRadio"] label {
            background: #ffffff;
            border: 1px solid var(--line);
            border-radius: 12px;
            padding: 9px 10px;
            margin-bottom: 7px;
        }

        div[data-testid="stRadio"] label:hover {
            border-color: #9bb6dd;
            background: #f7fbff;
        }
    </style>
    """,
    unsafe_allow_html=True,
)

def get_session():
    session = requests.Session()
    session.headers.update({"User-Agent": USER_AGENT})
    return session

def normalize_name(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip().lower()

def clean_html(value: str) -> str:
    text = re.sub(r"<script.*?</script>", "", value, flags=re.IGNORECASE | re.DOTALL)
    text = re.sub(r"<style.*?</style>", "", text, flags=re.IGNORECASE | re.DOTALL)
    text = re.sub(r"<[^>]+>", " ", text)
    text = html.unescape(text)
    text = re.sub(r"\s+", " ", text).strip()
    return text

def extract_profile_links_from_search_page(page: str):
    matches = re.findall(r'href="([^"]*athlete-biography\.html[^"]+)"', page, flags=re.IGNORECASE)
    results = []
    for href in matches:
        href = html.unescape(href).replace("&amp;", "&")
        if href.startswith("/"):
            href = FIS_PROFILE_PREFIX + href
        elif not href.startswith("http"):
            href = FIS_PROFILE_PREFIX + "/" + href.lstrip("/")
        if "sectorcode=al" not in href.lower() and "sector=al" not in href.lower():
            continue
        if href not in results:
            results.append(href)
    return results

def extract_profile_links_duckduckgo(page: str):
    pattern = re.compile(r'href="(.*?)"', re.IGNORECASE)
    raw_links = pattern.findall(page)
    results = []
    for link in raw_links:
        unescaped = html.unescape(link)
        if "uddg=" in unescaped:
            match = re.search(r"uddg=([^&]+)", unescaped)
            candidate = requests.utils.unquote(match.group(1)) if match else unescaped
        else:
            candidate = unescaped
        if "fis-ski.com/DB/general/athlete-biography.html" not in candidate:
            continue
        if "sectorcode=al" not in candidate.lower() and "sector=al" not in candidate.lower():
            continue
        candidate = candidate.replace("&amp;", "&")
        if candidate not in results:
            results.append(candidate)
    return results

def build_fis_search_urls(query: str):
    query = " ".join(query.split())
    is_code = query.isdigit()
    urls = []
    base_params = {
        "sectorcode": "AL",
        "search": "true",
        "birthyear": "",
        "gendercode": "",
        "nationcode": "",
        "skiclub": "",
        "skis": "",
        "status": "",
    }
    if is_code:
        params = dict(base_params)
        params["firstname"] = ""
        params["lastname"] = ""
        params["fiscode"] = query
        urls.append(f"{FIS_SEARCH_URL}?{urlencode(params)}")
        return urls

    parts = query.split()
    if len(parts) >= 2:
        params = dict(base_params)
        params["firstname"] = " ".join(parts[:-1])
        params["lastname"] = parts[-1]
        params["fiscode"] = ""
        urls.append(f"{FIS_SEARCH_URL}?{urlencode(params)}")

        params_rev = dict(base_params)
        params_rev["firstname"] = parts[-1]
        params_rev["lastname"] = " ".join(parts[:-1])
        params_rev["fiscode"] = ""
        urls.append(f"{FIS_SEARCH_URL}?{urlencode(params_rev)}")

    params_last = dict(base_params)
    params_last["firstname"] = ""
    params_last["lastname"] = query
    params_last["fiscode"] = ""
    urls.append(f"{FIS_SEARCH_URL}?{urlencode(params_last)}")

    params_first = dict(base_params)
    params_first["firstname"] = query
    params_first["lastname"] = ""
    params_first["fiscode"] = ""
    urls.append(f"{FIS_SEARCH_URL}?{urlencode(params_first)}")

    unique = []
    for url in urls:
        if url not in unique:
            unique.append(url)
    return unique

def extract_value(text: str, label: str):
    pattern = rf"{re.escape(label)}\s*:?\s*(.{{0,90}}?)(?=\s+[A-Z][A-Za-z\- ]{{2,25}}\s*:|\s+[A-Z][a-z]+\s+[A-Z][A-Za-z]+\s*:|$)"
    match = re.search(pattern, text, re.IGNORECASE)
    if not match:
        return "-"
    value = match.group(1).strip(" :-")
    value = re.sub(r"\s+", " ", value)
    return value if value else "-"

def extract_age(text: str):
    match = re.search(r"Age\s*:?\s*(\d{1,2})", text, re.IGNORECASE)
    return match.group(1) if match else "-"

@st.cache_data(ttl=900, show_spinner=False)
def fetch_profile(url: str):
    session = get_session()
    r = session.get(url, timeout=TIMEOUT)
    r.raise_for_status()
    page = r.text

    title_match = re.search(r"<h1[^>]*>(.*?)</h1>", page, re.IGNORECASE | re.DOTALL)
    name = clean_html(title_match.group(1)) if title_match else "Unbekannter Athlet"
    clean_page = clean_html(page)
    competitor_match = re.search(r"competitorid=(\d+)", url, re.IGNORECASE)
    competitor_id = competitor_match.group(1) if competitor_match else "-"

    return {
        "name": name,
        "nation": extract_value(clean_page, "Nation"),
        "fis_code": extract_value(clean_page, "FIS Code"),
        "birthdate": extract_value(clean_page, "Birthdate"),
        "age": extract_age(clean_page),
        "club": extract_value(clean_page, "Club"),
        "residence": extract_value(clean_page, "Residence"),
        "place_of_birth": extract_value(clean_page, "Birth Place"),
        "status": extract_value(clean_page, "Status"),
        "gender": extract_value(clean_page, "Gender"),
        "skis": extract_value(clean_page, "Skis"),
        "boots": extract_value(clean_page, "Boots"),
        "poles": extract_value(clean_page, "Poles"),
        "helmet": extract_value(clean_page, "Helmet"),
        "goggles": extract_value(clean_page, "Goggles"),
        "gloves": extract_value(clean_page, "Gloves"),
        "racing_suit": extract_value(clean_page, "Racing suit"),
        "competitor_id": competitor_id,
        "url": url,
    }

@st.cache_data(ttl=900, show_spinner=True)
def search_athletes(query: str):
    query = " ".join(query.split())
    if not query:
        return []
    session = get_session()
    profile_links = []

    for url in build_fis_search_urls(query):
        try:
            response = session.get(url, timeout=TIMEOUT)
            response.raise_for_status()
            profile_links.extend(extract_profile_links_from_search_page(response.text))
        except Exception:
            pass

    if not profile_links:
        ddg_query = (
            'site:fis-ski.com/DB/general/athlete-biography.html '
            '"sectorcode=AL" '
            f'"{query}"'
        )
        response = session.get(DUCKDUCKGO_HTML, params={"q": ddg_query}, timeout=TIMEOUT)
        response.raise_for_status()
        profile_links.extend(extract_profile_links_duckduckgo(response.text))

    unique_links = []
    for link in profile_links:
        if link not in unique_links:
            unique_links.append(link)

    athletes = []
    seen = set()
    is_code = query.isdigit()
    q = normalize_name(query)
    parts = [p for p in q.split() if p]

    def score(athlete):
        name = normalize_name(athlete.get("name", ""))
        value = 0
        if q == name:
            value += 100
        if q in name:
            value += 60
        if parts and all(p in name for p in parts):
            value += 40
        if is_code and athlete.get("fis_code") == query:
            value += 140
        return value

    for link in unique_links[:25]:
        try:
            athlete = fetch_profile(link)
        except Exception:
            continue
        unique_key = (
            athlete.get("name", "").strip().lower(),
            athlete.get("fis_code", "").strip(),
            athlete.get("competitor_id", "").strip(),
        )
        if unique_key in seen:
            continue
        seen.add(unique_key)
        athlete["score"] = score(athlete)
        athletes.append(athlete)

    athletes.sort(key=lambda a: a.get("score", 0), reverse=True)
    if is_code:
        exact = [a for a in athletes if a.get("fis_code") == query]
        if exact:
            return exact[:12]
    return athletes[:12]

@st.cache_data(ttl=900, show_spinner=False)
def fetch_recent_results(athlete_url: str):
    session = get_session()
    r = session.get(athlete_url, timeout=TIMEOUT)
    r.raise_for_status()
    tables = pd.read_html(r.text)
    frames = []
    for df in tables:
        cols = [str(c).strip() for c in df.columns]
        low = " | ".join(cols).lower()
        if any(k in low for k in ["date", "place", "event", "discipline", "rank", "result", "points"]):
            df.columns = cols
            frames.append(df)
    if not frames:
        return None
    results = pd.concat(frames, ignore_index=True).dropna(how="all")
    wanted = []
    for col in results.columns:
        low = col.lower()
        if any(k in low for k in ["date", "place", "event", "discipline", "rank", "result", "points", "nation"]):
            wanted.append(col)
    if wanted:
        results = results[wanted]
    return results.head(25)

def summarize_results(df: pd.DataFrame):
    if df is None or df.empty:
        return {"starts": "0", "top10": "-", "best": "-", "disciplines": "-"}
    starts = len(df)
    best = "-"
    top10 = "-"
    rank_col = None
    for col in df.columns:
        if "rank" in col.lower() or "place" in col.lower():
            rank_col = col
            break
    if rank_col:
        numeric = pd.to_numeric(df[rank_col], errors="coerce")
        if numeric.notna().any():
            best = str(int(numeric.min()))
            top10 = str(int((numeric <= 10).sum()))
    disc_cols = [c for c in df.columns if "discipline" in c.lower() or "event" in c.lower()]
    disciplines = "-"
    if disc_cols:
        vals = df[disc_cols[0]].dropna().astype(str).head(5).tolist()
        disciplines = ", ".join(vals[:3]) if vals else "-"
    return {"starts": str(starts), "top10": top10, "best": best, "disciplines": disciplines}

def metric_card(label: str, value: str):
    st.markdown(
        f'<div class="metric-card"><div class="metric-label">{label}</div><div class="metric-value">{value}</div></div>',
        unsafe_allow_html=True,
    )

def kpi_card(label: str, value: str):
    st.markdown(
        f'<div class="kpi"><div class="kpi-label">{label}</div><div class="kpi-value">{value}</div></div>',
        unsafe_allow_html=True,
    )

if "results" not in st.session_state:
    st.session_state.results = []
if "selected_index" not in st.session_state:
    st.session_state.selected_index = 0
if "active_view" not in st.session_state:
    st.session_state.active_view = "Athletendaten"

# Full-width header
st.markdown('<div class="header-shell">', unsafe_allow_html=True)
h1, h2, h3 = st.columns([2.4, 5.2, 0.8])
with h1:
    s1, s2 = st.columns([3.1, 1.45])
    with s1:
        search_query = st.text_input("", placeholder="Athlet oder FIS-Code suchen…", label_visibility="collapsed")
    with s2:
        search_button = st.button("Suchen", use_container_width=True)
with h2:
    st.markdown(f'<div class="header-title">{APP_NAME}</div>', unsafe_allow_html=True)
with h3:
    st.markdown(f'<div class="header-version">{APP_VERSION}</div>', unsafe_allow_html=True)
st.markdown('</div>', unsafe_allow_html=True)

# Persistent left navigation under header
with st.sidebar:
    st.markdown("## Navigation")
    st.session_state.active_view = st.radio(
        "Bereich",
        ["Athletendaten", "Rennauswertung", "FIS-Punkte", "Ergebnisse"],
        label_visibility="collapsed",
    )
    st.markdown("---")
    st.markdown('<div class="nav-caption">Die Navigation bleibt immer sichtbar und liegt unter der Kopfzeile.</div>', unsafe_allow_html=True)

if search_button:
    if not search_query.strip():
        st.warning("Bitte gib einen Athletennamen oder einen FIS-Code ein.")
    else:
        with st.spinner("Athleten werden gesucht ..."):
            st.session_state.results = search_athletes(search_query)
            st.session_state.selected_index = 0
        if not st.session_state.results:
            st.warning("Kein passender Alpine-Athlet gefunden.")

results = st.session_state.results
selected_athlete = results[st.session_state.selected_index] if results else None

left, right = st.columns([1.05, 2.15])

with left:
    st.markdown('<div class="content-title">Trefferliste</div>', unsafe_allow_html=True)
    if not results:
        st.info("Noch keine Treffer. Suche oben nach einem Athleten.")
    else:
        labels = [f"{a['name']} | {a['nation']} | FIS-Code: {a['fis_code']}" for a in results]
        idx = st.radio(
            "Treffer auswählen",
            options=list(range(len(labels))),
            format_func=lambda i: labels[i],
            index=min(st.session_state.selected_index, len(labels)-1),
            label_visibility="collapsed",
        )
        st.session_state.selected_index = idx
        selected_athlete = results[idx]

with right:
    if st.session_state.active_view == "Athletendaten":
        st.markdown('<div class="content-title">Athletendaten</div>', unsafe_allow_html=True)
        if not selected_athlete:
            st.info("Sobald ein Athlet gefunden wird, erscheinen hier die Athletendaten.")
        else:
            hero = (
                '<div class="hero-card">'
                f'<div class="hero-name">{selected_athlete["name"]}</div>'
                f'<div class="hero-meta">{selected_athlete["nation"]} | FIS-Code {selected_athlete["fis_code"]} | Competitor ID {selected_athlete["competitor_id"]}</div>'
                '</div>'
            )
            st.markdown(hero, unsafe_allow_html=True)

            row1 = st.columns(4)
            summary = [
                ("Nation", selected_athlete["nation"]),
                ("FIS-Code", selected_athlete["fis_code"]),
                ("Alter", selected_athlete["age"]),
                ("Status", selected_athlete["status"]),
            ]
            for col, (label, value) in zip(row1, summary):
                with col:
                    kpi_card(label, value)

            metric_rows = [
                [("Geburtsdatum", selected_athlete["birthdate"]), ("Geschlecht", selected_athlete["gender"]), ("Club", selected_athlete["club"])],
                [("Wohnort", selected_athlete["residence"]), ("Geburtsort", selected_athlete["place_of_birth"]), ("Skis", selected_athlete["skis"])],
                [("Boots", selected_athlete["boots"]), ("Poles", selected_athlete["poles"]), ("Helmet", selected_athlete["helmet"])],
                [("Goggles", selected_athlete["goggles"]), ("Gloves", selected_athlete["gloves"]), ("Racing Suit", selected_athlete["racing_suit"])],
            ]
            for row in metric_rows:
                cols = st.columns(3)
                for col, (label, value) in zip(cols, row):
                    with col:
                        metric_card(label, value)
            st.link_button("Offizielles FIS-Profil öffnen", selected_athlete["url"])

    elif st.session_state.active_view == "Rennauswertung":
        st.markdown('<div class="content-title">Rennauswertung</div>', unsafe_allow_html=True)
        if not selected_athlete:
            st.info("Suche zuerst einen Athleten.")
        else:
            st.markdown('<div class="panel-note">Dieses Modul ist als klarer Platzhalter für die spätere Rennauswertung vorbereitet. Hier können später Split-Zeiten, Platzierungsanalyse und Fehlerbilder ergänzt werden.</div>', unsafe_allow_html=True)
            c1, c2, c3 = st.columns(3)
            with c1:
                kpi_card("Analyse-Status", "Vorbereitet")
            with c2:
                kpi_card("Athlet", selected_athlete["name"])
            with c3:
                kpi_card("Nation", selected_athlete["nation"])

    elif st.session_state.active_view == "FIS-Punkte":
        st.markdown('<div class="content-title">FIS-Punkte</div>', unsafe_allow_html=True)
        if not selected_athlete:
            st.info("Suche zuerst einen Athleten.")
        else:
            st.markdown('<div class="panel-note">Dieser Bereich ist für die spätere FIS-Punkte-Analyse vorbereitet. Hier können Disziplin-Punkte, Entwicklungen und Trenddiagramme eingebaut werden.</div>', unsafe_allow_html=True)
            c1, c2, c3 = st.columns(3)
            with c1:
                kpi_card("Athlet", selected_athlete["name"])
            with c2:
                kpi_card("FIS-Code", selected_athlete["fis_code"])
            with c3:
                kpi_card("Modul", "Vorbereitet")

    elif st.session_state.active_view == "Ergebnisse":
        st.markdown('<div class="content-title">Ergebnisse</div>', unsafe_allow_html=True)
        if not selected_athlete:
            st.info("Suche zuerst einen Athleten.")
        else:
            st.markdown(
                f'<div class="mini-card"><strong>{selected_athlete["name"]}</strong><br>{selected_athlete["nation"]} | FIS-Code {selected_athlete["fis_code"]}</div>',
                unsafe_allow_html=True,
            )
            try:
                results_df = fetch_recent_results(selected_athlete["url"])
            except Exception as exc:
                results_df = None
                st.warning(f"Ergebnisse konnten nicht geladen werden: {exc}")

            summary = summarize_results(results_df)
            s1, s2, s3, s4 = st.columns(4)
            with s1:
                kpi_card("Erkannte Starts", summary["starts"])
            with s2:
                kpi_card("Top 10", summary["top10"])
            with s3:
                kpi_card("Beste Platzierung", summary["best"])
            with s4:
                kpi_card("Disziplinen", summary["disciplines"])

            if results_df is None or results_df.empty:
                st.info("Auf der Profilseite konnte keine direkt auslesbare Ergebnis-Tabelle gefunden werden.")
            else:
                st.markdown('<div class="panel-note">Die untenstehende Tabelle wurde direkt aus der Athletenseite erkannt und für die App zusammengeführt.</div>', unsafe_allow_html=True)
                st.dataframe(results_df, use_container_width=True, hide_index=True)

st.markdown('<div class="footer-note">Aktueller Fokus: klare Tool-Struktur mit Kopfzeile, permanenter Navigation und sauber getrennten Analysebereichen.</div>', unsafe_allow_html=True)
