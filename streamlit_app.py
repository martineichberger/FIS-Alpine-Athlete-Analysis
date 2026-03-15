import html
import re
from urllib.parse import urlencode, quote_plus

import requests
import streamlit as st
import pandas as pd

APP_NAME = "FIS-Alpine-Athlete-Analysis"
APP_VERSION = "v3.2-streamlit"
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
        .stApp {
            background: linear-gradient(180deg, #08101d 0%, #0b1220 100%);
        }
        .header-wrap {
            background: linear-gradient(90deg,#0f1b33 0%, #162a52 100%);
            border: 1px solid #23375a;
            border-radius: 20px;
            padding: 14px 18px;
            margin-bottom: 18px;
            box-shadow: 0 10px 30px rgba(0,0,0,0.18);
        }
        .app-title {
            font-size: 1.95rem;
            font-weight: 800;
            text-align: center;
            color: #e6eefc;
            letter-spacing: 0.3px;
            line-height: 1.2;
            margin-top: 0.15rem;
        }
        .app-subtitle {
            text-align: center;
            color: #95a8c9;
            font-size: 0.95rem;
            margin-top: 0.25rem;
        }
        .section-title {
            font-size: 1.15rem;
            font-weight: 800;
            margin-bottom: 0.6rem;
        }
        .metric-card {
            background: linear-gradient(180deg, #0f1b33 0%, #101a2d 100%);
            border: 1px solid #23375a;
            border-radius: 18px;
            padding: 14px 14px 12px 14px;
            margin-bottom: 0.85rem;
            min-height: 94px;
        }
        .metric-label {
            color: #95a8c9;
            font-size: 0.78rem;
            margin-bottom: 0.25rem;
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }
        .metric-value {
            color: #e6eefc;
            font-size: 1.02rem;
            font-weight: 800;
            line-height: 1.25;
            word-break: break-word;
        }
        .hero-card {
            background: linear-gradient(180deg, #0e1a31 0%, #0f1b33 100%);
            border: 1px solid #23375a;
            border-radius: 22px;
            padding: 18px;
            margin-bottom: 1rem;
        }
        .hero-name {
            color: #e6eefc;
            font-size: 1.8rem;
            font-weight: 900;
            line-height: 1.15;
        }
        .hero-meta {
            color: #95a8c9;
            font-size: 0.97rem;
            margin-top: 0.45rem;
        }
        .mini-card {
            background: #0d172a;
            border: 1px solid #23375a;
            border-radius: 16px;
            padding: 12px;
            min-height: 88px;
            margin-bottom: 0.75rem;
        }
        .kpi {
            background: linear-gradient(180deg, #122243 0%, #0d172b 100%);
            border: 1px solid #23375a;
            border-radius: 18px;
            padding: 14px;
            margin-bottom: 0.8rem;
        }
        .kpi-label {
            color: #95a8c9;
            font-size: 0.78rem;
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }
        .kpi-value {
            color: #e6eefc;
            font-size: 1.35rem;
            font-weight: 900;
            margin-top: 0.25rem;
        }
        .footer-note {
            color: #95a8c9;
            font-size: 0.86rem;
            margin-top: 1rem;
        }
        .result-panel {
            background: #0d172a;
            border: 1px solid #23375a;
            border-radius: 18px;
            padding: 14px;
            margin-bottom: 1rem;
        }
        div[data-testid="stRadio"] label {
            background: #0d172b;
            border: 1px solid #23375a;
            border-radius: 14px;
            padding: 10px 12px;
            margin-bottom: 8px;
        }
        div[data-testid="stRadio"] label:hover {
            border-color: #3964a3;
            background: #10203d;
        }
        div[data-testid="stTextInput"] input {
            border-radius: 14px !important;
        }
        div.stButton > button {
            border-radius: 14px !important;
            font-weight: 700 !important;
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
    page = r.text

    tables = pd.read_html(page)
    frames = []
    for df in tables:
        columns = [str(c).strip() for c in df.columns]
        cols_lower = " | ".join(columns).lower()
        if any(k in cols_lower for k in ["date", "place", "event", "rank", "nation", "points"]):
            df.columns = columns
            frames.append(df)

    if not frames:
        return None

    results = pd.concat(frames, ignore_index=True)
    results = results.dropna(how="all")
    results.columns = [str(c).strip() for c in results.columns]

    wanted = []
    for col in results.columns:
        low = col.lower()
        if any(k in low for k in ["date", "place", "event", "discipline", "rank", "result", "points", "nation"]):
            wanted.append(col)

    if wanted:
        results = results[wanted]

    results = results.head(25)
    return results


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


def summarize_results(df: pd.DataFrame):
    if df is None or df.empty:
        return {"starts": "0", "top10": "-", "best": "-", "disciplines": "-"}

    starts = len(df)

    best = "-"
    rank_col = None
    for col in df.columns:
        if "rank" in col.lower() or "place" in col.lower():
            rank_col = col
            break

    if rank_col:
        numeric = pd.to_numeric(df[rank_col], errors="coerce")
        if numeric.notna().any():
            best_val = int(numeric.min())
            best = str(best_val)
            top10 = str(int((numeric <= 10).sum()))
        else:
            top10 = "-"
    else:
        top10 = "-"

    disc_cols = [c for c in df.columns if "discipline" in c.lower() or "event" in c.lower()]
    if disc_cols:
        vals = df[disc_cols[0]].dropna().astype(str).head(5).tolist()
        disciplines = ", ".join(vals[:3]) if vals else "-"
    else:
        disciplines = "-"

    return {
        "starts": str(starts),
        "top10": top10,
        "best": best,
        "disciplines": disciplines
    }


if "results" not in st.session_state:
    st.session_state.results = []
if "selected_index" not in st.session_state:
    st.session_state.selected_index = 0
if "active_view" not in st.session_state:
    st.session_state.active_view = "Dashboard"

with st.sidebar:
    st.markdown("## Navigation")
    st.session_state.active_view = st.radio(
        "Ansicht",
        ["Dashboard", "Athletenprofil", "Vergleich", "Resultate"],
        label_visibility="collapsed",
    )
    st.markdown("---")
    st.caption("Der Resultate-Tab zeigt jetzt die erkannten Resultat-Tabellen der Athletenseite, sofern sie auf der Profilseite direkt auslesbar sind.")

st.markdown('<div class="header-wrap">', unsafe_allow_html=True)
c1, c2, c3 = st.columns([2.4, 4.8, 0.8])
with c1:
    q_col, b_col = st.columns([3.2, 1.4])
    with q_col:
        search_query = st.text_input("", placeholder="Athlet oder FIS-Code suchen…", label_visibility="collapsed")
    with b_col:
        search_button = st.button("Suchen", use_container_width=True)
with c2:
    st.markdown(
        f'<div class="app-title">{APP_NAME}</div><div class="app-subtitle">Modernes Analyse-Dashboard für FIS Alpine Athleten</div>',
        unsafe_allow_html=True,
    )
with c3:
    st.markdown(
        f'<div style="text-align:right; color:#9bb0d3; padding-top:0.65rem;">{APP_VERSION}</div>',
        unsafe_allow_html=True,
    )
st.markdown('</div>', unsafe_allow_html=True)

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

if st.session_state.active_view == "Dashboard":
    left, right = st.columns([1.05, 2.15])

    with left:
        st.markdown('<div class="section-title">Trefferliste</div>', unsafe_allow_html=True)
        if not results:
            st.info("Noch keine Treffer. Suche oben nach einem Athleten.")
        else:
            labels = [f"{a['name']} | {a['nation']} | FIS-Code: {a['fis_code']}" for a in results]
            idx = st.radio(
                "Treffer auswählen",
                options=list(range(len(labels))),
                format_func=lambda i: labels[i],
                index=min(st.session_state.selected_index, len(labels) - 1),
                label_visibility="collapsed",
            )
            st.session_state.selected_index = idx
            selected_athlete = results[idx]

    with right:
        if not selected_athlete:
            st.info("Sobald ein Athlet gefunden wird, erscheint hier das Dashboard.")
        else:
            hero = (
                '<div class="hero-card">'
                f'<div class="hero-name">{selected_athlete["name"]}</div>'
                f'<div class="hero-meta">{selected_athlete["nation"]} | FIS-Code {selected_athlete["fis_code"]} | Competitor ID {selected_athlete["competitor_id"]}</div>'
                '</div>'
            )
            st.markdown(hero, unsafe_allow_html=True)

            k1, k2, k3, k4 = st.columns(4)
            with k1:
                kpi_card("Nation", selected_athlete["nation"])
            with k2:
                kpi_card("FIS-Code", selected_athlete["fis_code"])
            with k3:
                kpi_card("Alter", selected_athlete["age"])
            with k4:
                kpi_card("Status", selected_athlete["status"])

            st.markdown('<div class="section-title">Athletenübersicht</div>', unsafe_allow_html=True)
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

            a1, a2 = st.columns([1, 1.6])
            with a1:
                st.link_button("Offizielles FIS-Profil öffnen", selected_athlete["url"], use_container_width=True)
            with a2:
                st.caption("Dashboard-Struktur ist bereit für Resultate, FIS-Punkte und Vergleiche.")

elif st.session_state.active_view == "Athletenprofil":
    st.markdown('<div class="section-title">Athletenprofil</div>', unsafe_allow_html=True)
    if not selected_athlete:
        st.info("Suche zuerst einen Athleten.")
    else:
        hero = (
            '<div class="hero-card">'
            f'<div class="hero-name">{selected_athlete["name"]}</div>'
            f'<div class="hero-meta">{selected_athlete["nation"]} | FIS-Code {selected_athlete["fis_code"]}</div>'
            '</div>'
        )
        st.markdown(hero, unsafe_allow_html=True)

        metrics = [
            ("Nation", selected_athlete["nation"]),
            ("FIS-Code", selected_athlete["fis_code"]),
            ("Competitor ID", selected_athlete["competitor_id"]),
            ("Alter", selected_athlete["age"]),
            ("Geburtsdatum", selected_athlete["birthdate"]),
            ("Status", selected_athlete["status"]),
            ("Club", selected_athlete["club"]),
            ("Wohnort", selected_athlete["residence"]),
        ]
        for start in range(0, len(metrics), 4):
            cols = st.columns(4)
            for col, (label, value) in zip(cols, metrics[start:start + 4]):
                with col:
                    metric_card(label, value)
        st.link_button("FIS-Profil öffnen", selected_athlete["url"])

elif st.session_state.active_view == "Vergleich":
    st.markdown('<div class="section-title">Vergleich</div>', unsafe_allow_html=True)
    st.info("Dieses Modul ist als nächster Ausbauschritt vorbereitet.")
    if results:
        c1, c2 = st.columns(2)
        with c1:
            kpi_card("Aktuell ausgewählt", results[st.session_state.selected_index]["name"])
        with c2:
            kpi_card("Treffer im Speicher", str(len(results)))

elif st.session_state.active_view == "Resultate":
    st.markdown('<div class="section-title">Resultate</div>', unsafe_allow_html=True)
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
            st.warning(f"Resultate konnten nicht geladen werden: {exc}")

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
            st.info("Auf der Profilseite konnte keine direkt auslesbare Resultat-Tabelle gefunden werden. Als nächster Schritt kann ein gezielterer Resultat-Parser eingebaut werden.")
        else:
            st.markdown('<div class="result-panel">Die untenstehenden Tabellen wurden direkt aus der Athletenseite erkannt und für die Analyse zusammengeführt.</div>', unsafe_allow_html=True)
            st.dataframe(results_df, use_container_width=True, hide_index=True)

st.markdown('<div class="footer-note">Aktueller Fokus: stabile Athletensuche, moderner App-Aufbau und erste Resultatendarstellung.</div>', unsafe_allow_html=True)
