import html
import re
from datetime import datetime
from urllib.parse import urlencode

import pandas as pd
import requests
import streamlit as st

APP_NAME = "FIS-Alpine-Athlete-Analysis"
APP_VERSION = "v5.1-streamlit"
USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/122.0.0.0 Safari/537.36"
)
TIMEOUT = 25
FIS_SEARCH_URL = "https://www.fis-ski.com/DB/general/biographies.html"
FIS_PROFILE_PREFIX = "https://www.fis-ski.com"
DUCKDUCKGO_HTML = "https://html.duckduckgo.com/html/"

DISCIPLINES = [
    "Team Combined",
    "Parallel Team",
    "Parallel",
    "Alpine Combined",
    "Combined",
    "Giant Slalom",
    "Super G",
    "Downhill",
    "Slalom",
]
CATEGORY_LABELS = [
    "Olympic Winter Games",
    "World Championships",
    "World Cup",
    "European Cup",
    "South American Cup",
    "North American Cup",
    "Far East Cup",
    "Australia New Zealand Cup",
    "National Championships",
    "National Junior Championships",
    "National Junior Race",
    "University",
    "CIT",
    "FIS",
    "Training",
]

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
            --line: #d8e1ef;
            --text: #102038;
            --muted: #64748b;
            --card: #ffffff;
        }
        .stApp { background: #ffffff; }
        [data-testid="stSidebar"] { display:none; }
        .header-shell { background: var(--navy); margin: -1rem -1rem 1rem -1rem; width: calc(100% + 2rem); padding: 0.8rem 1.2rem; border-bottom: 1px solid #274a7f; }
        .header-title { color: #ffffff; font-size: 1.45rem; font-weight: 800; text-align: center; line-height: 1.2; margin-top: 0.2rem; }
        .header-version { color: #cddaf0; text-align: right; font-size: 0.9rem; padding-top: 0.35rem; }
        .content-title { color: var(--text); font-size: 1.15rem; font-weight: 800; margin-bottom: 0.75rem; }
        .hero-card { background: var(--card); border: 1px solid var(--line); border-radius: 18px; padding: 1rem 1.1rem; margin-bottom: 1rem; box-shadow: 0 2px 14px rgba(16, 32, 56, 0.05); }
        .hero-name { color: var(--text); font-size: 1.65rem; font-weight: 900; line-height: 1.1; }
        .hero-meta { color: var(--muted); font-size: 0.95rem; margin-top: 0.35rem; }
        .metric-card { background: #ffffff; border: 1px solid var(--line); border-radius: 16px; padding: 0.9rem 1rem; margin-bottom: 0.8rem; min-height: 92px; box-shadow: 0 2px 10px rgba(16, 32, 56, 0.04); }
        .metric-label { color: var(--muted); font-size: 0.76rem; text-transform: uppercase; letter-spacing: 0.4px; margin-bottom: 0.25rem; }
        .metric-value { color: var(--text); font-size: 1rem; font-weight: 800; line-height: 1.25; word-break: break-word; }
        .kpi { background: #f7f9fc; border: 1px solid var(--line); border-radius: 16px; padding: 0.9rem 1rem; margin-bottom: 0.8rem; }
        .kpi-label { color: var(--muted); font-size: 0.76rem; text-transform: uppercase; letter-spacing: 0.4px; }
        .kpi-value { color: var(--text); font-size: 1.3rem; font-weight: 900; margin-top: 0.2rem; }
        .panel-note { background: #f8fbff; border: 1px solid var(--line); color: var(--muted); border-radius: 14px; padding: 0.8rem 0.95rem; margin-bottom: 1rem; }
        .mini-card { background: #ffffff; border: 1px solid var(--line); border-radius: 16px; padding: 0.9rem; margin-bottom: 0.8rem; }
        .footer-note { color: var(--muted); font-size: 0.86rem; margin-top: 1rem; }
        .nav-caption { color: var(--muted); font-size: 0.85rem; margin-top: 0.25rem; }
        .search-panel { background:#ffffff; border:1px solid var(--line); border-radius:18px; padding:1rem; margin-bottom:1rem; box-shadow: 0 2px 10px rgba(16, 32, 56, 0.04); }
        div[data-testid="stTextInput"] input { border-radius: 12px !important; border: 1px solid #c9d5e7 !important; }
        div.stButton > button, div[data-testid="stFormSubmitButton"] button { border-radius: 12px !important; font-weight: 700 !important; width:100%; }
        div[data-testid="stRadio"] label { background: #ffffff; border: 1px solid var(--line); border-radius: 12px; padding: 9px 10px; margin-bottom: 7px; }
        div[data-testid="stRadio"] label:hover { border-color: #9bb6dd; background: #f7fbff; }
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


def country_code_to_flag(code: str) -> str:
    code = (code or "").strip().upper()
    if len(code) != 3 or not code.isalpha():
        return ""
    special = {
        "AUT": "🇦🇹", "GER": "🇩🇪", "SUI": "🇨🇭", "ITA": "🇮🇹", "FRA": "🇫🇷",
        "USA": "🇺🇸", "CAN": "🇨🇦", "NOR": "🇳🇴", "SWE": "🇸🇪", "FIN": "🇫🇮",
        "SLO": "🇸🇮", "CRO": "🇭🇷", "CZE": "🇨🇿", "SVK": "🇸🇰", "POL": "🇵🇱",
        "GBR": "🇬🇧", "ESP": "🇪🇸", "AND": "🇦🇩", "JPN": "🇯🇵", "KOR": "🇰🇷",
        "CHN": "🇨🇳", "AUS": "🇦🇺", "NZL": "🇳🇿", "ARG": "🇦🇷", "CHI": "🇨🇱"
    }
    return special.get(code, "")


def split_name(title_name: str):
    title_name = re.sub(r"\s+", " ", (title_name or "").strip())
    if not title_name:
        return "-", "-"
    parts = title_name.split()
    uppercase_parts = [p for p in parts if p.isupper()]
    if uppercase_parts:
        last_name = " ".join(uppercase_parts)
        first_name = " ".join([p for p in parts if not p.isupper()]).strip()
        if first_name:
            return last_name, first_name
    if len(parts) >= 2:
        return parts[-1], " ".join(parts[:-1])
    return title_name, "-"


def extract_nation_from_page(page: str, clean_page: str):
    code_match = re.search(r">\s*([A-Z]{3})\s+([A-Z][a-zA-Z\-]+(?:\s+[A-Z][a-zA-Z\-]+)?)\s*<", page)
    if code_match:
        code = code_match.group(1).strip()
        name = code_match.group(2).strip()
        return code, name
    text_match = re.search(r"\b([A-Z]{3})\s+([A-Z][a-zA-Z\-]+(?:\s+[A-Z][a-zA-Z\-]+)?)\b", clean_page)
    if text_match:
        code = text_match.group(1).strip()
        name = text_match.group(2).strip()
        return code, name
    nation_label = extract_value(clean_page, "Nation")
    if nation_label and nation_label != "-":
        parts = nation_label.split(" ", 1)
        if len(parts) == 2 and len(parts[0]) == 3 and parts[0].isalpha():
            return parts[0].upper(), parts[1].strip()
        return "-", nation_label.strip()
    return "-", "-"


@st.cache_data(ttl=900, show_spinner=False)
def fetch_profile(url: str):
    session = get_session()
    r = session.get(url, timeout=TIMEOUT)
    r.raise_for_status()
    page = r.text

    title_match = re.search(r"<h1[^>]*>(.*?)</h1>", page, re.IGNORECASE | re.DOTALL)
    raw_name = clean_html(title_match.group(1)) if title_match else "Unbekannter Athlet"
    last_name, first_name = split_name(raw_name)
    clean_page = clean_html(page)
    competitor_match = re.search(r"competitorid=(\d+)", url, re.IGNORECASE)
    competitor_id = competitor_match.group(1) if competitor_match else "-"
    nation_code, nation_name = extract_nation_from_page(page, clean_page)
    nation_flag = country_code_to_flag(nation_code)
    club = extract_value(clean_page, "Club")
    if club == "-":
        club_match = re.search(r"</h1>\s*([^<]{3,120})<", page, re.IGNORECASE | re.DOTALL)
        if club_match:
            club_candidate = clean_html(club_match.group(1))
            if club_candidate and len(club_candidate) <= 80:
                club = club_candidate
    return {
        "name": raw_name,
        "last_name": last_name,
        "first_name": first_name,
        "nation_code": nation_code,
        "nation_name": nation_name,
        "nation_flag": nation_flag,
        "birthdate": extract_value(clean_page, "Birthdate"),
        "age": extract_age(clean_page),
        "club": club,
        "gender": extract_value(clean_page, "Gender"),
        "fis_code": extract_value(clean_page, "FIS Code"),
        "status": extract_value(clean_page, "Status"),
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
        try:
            ddg_query = (
                'site:fis-ski.com/DB/general/athlete-biography.html '
                '"sectorcode=AL" '
                f'"{query}"'
            )
            response = session.get(DUCKDUCKGO_HTML, params={"q": ddg_query}, timeout=TIMEOUT)
            response.raise_for_status()
            profile_links.extend(extract_profile_links_duckduckgo(response.text))
        except Exception:
            pass

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
        if is_code and str(athlete.get("fis_code", "")).strip() == query:
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
        exact = [a for a in athletes if str(a.get("fis_code", "")).strip() == query]
        if exact:
            return exact[:12]
    return athletes[:12]


def results_url_from_profile(athlete_url: str) -> str:
    if "type=result" in athlete_url:
        return athlete_url
    if "?" in athlete_url:
        return athlete_url + "&type=result"
    return athlete_url + "?type=result"


def compute_season(date_str: str):
    try:
        dt = datetime.strptime(date_str, "%d-%m-%Y")
    except Exception:
        return None
    return dt.year + 1 if dt.month >= 7 else dt.year


def extract_discipline(text: str):
    lower = text.lower()
    best = None
    best_pos = -1
    for d in DISCIPLINES:
        pos = lower.rfind(d.lower())
        if pos > best_pos:
            best = d
            best_pos = pos
    return best, best_pos


def parse_result_line(text: str):
    text = re.sub(r"\s+", " ", text).strip()
    if not re.match(r"^\d{2}-\d{2}-\d{4}\s", text):
        return None

    date_str = text[:10]
    discipline, discipline_pos = extract_discipline(text)
    if not discipline:
        return None

    after = text[discipline_pos + len(discipline):].strip()
    tokens = after.split()

    position = "-"
    fis_points = "-"
    cup_points = "-"
    if tokens:
        position = tokens[0]
    numeric_tokens = [t for t in tokens[1:] if re.match(r"^\d+(\.\d+)?$", t)]
    if len(numeric_tokens) >= 1:
        fis_points = numeric_tokens[0]
    if len(numeric_tokens) >= 2:
        cup_points = numeric_tokens[1]

    category = "-"
    for cat in CATEGORY_LABELS:
        if cat.lower() in text.lower():
            category = cat
            break

    nation = "-"
    before_disc = text[10:discipline_pos]
    codes = re.findall(r"\b([A-Z]{3})\b", before_disc)
    if codes:
        nation = codes[-1]
    else:
        codes = re.findall(r"\b([A-Z]{3})\b", text[10:])
        if codes:
            nation = codes[0]

    season = compute_season(date_str)

    return {
        "Datum": date_str,
        "Saison": season if season is not None else "-",
        "Disziplin": discipline,
        "Kategorie": category,
        "Nation": nation,
        "Position": position,
        "FIS-Punkte": fis_points,
        "Cup-Punkte": cup_points,
        "Raw": text,
    }


@st.cache_data(ttl=900, show_spinner=False)
def fetch_result_entries(athlete_url: str):
    url = results_url_from_profile(athlete_url)
    session = get_session()
    r = session.get(url, timeout=TIMEOUT)
    r.raise_for_status()
    page = r.text

    candidates = []
    anchors = re.findall(r"<a[^>]*>(.*?)</a>", page, flags=re.IGNORECASE | re.DOTALL)
    candidates.extend(clean_html(a) for a in anchors)
    blocks = re.findall(r">(.*?)<", page, flags=re.IGNORECASE | re.DOTALL)
    candidates.extend(clean_html(b) for b in blocks if re.search(r"\d{2}-\d{2}-\d{4}", clean_html(b)))

    entries = []
    seen = set()
    for text in candidates:
        parsed = parse_result_line(text)
        if not parsed:
            continue
        key = (parsed["Datum"], parsed["Disziplin"], parsed["Position"], parsed["Raw"])
        if key in seen:
            continue
        seen.add(key)
        entries.append(parsed)

    if not entries:
        return None

    df = pd.DataFrame(entries)
    df["SortDate"] = pd.to_datetime(df["Datum"], format="%d-%m-%Y", errors="coerce")
    df = df.sort_values(["SortDate", "Disziplin", "Kategorie"], ascending=[False, True, True]).reset_index(drop=True)
    return df


def summarize_results(df: pd.DataFrame):
    if df is None or df.empty:
        return {"starts": "0", "top10": "-", "best": "-", "disciplines": "-"}
    starts = len(df)
    numeric = pd.to_numeric(df["Position"], errors="coerce")
    best = str(int(numeric.min())) if numeric.notna().any() else "-"
    top10 = str(int((numeric <= 10).sum())) if numeric.notna().any() else "-"
    disciplines = ", ".join(df["Disziplin"].dropna().astype(str).unique()[:4]) if "Disziplin" in df else "-"
    return {"starts": str(starts), "top10": top10, "best": best, "disciplines": disciplines or "-"}


def starts_by_discipline(df: pd.DataFrame):
    if df is None or df.empty:
        return pd.DataFrame(columns=["Disziplin", "Starts"])
    return (
        df.groupby("Disziplin", dropna=False)
        .size()
        .reset_index(name="Starts")
        .sort_values(["Starts", "Disziplin"], ascending=[False, True])
        .reset_index(drop=True)
    )


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


def init_state():
    defaults = {
        "results": [],
        "selected_index": 0,
        "active_view": "Athletendaten",
        "search_query": "",
        "last_query": "",
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


init_state()

st.markdown(
    f'''
    <div style="background:#102649;color:white;padding:14px 22px;margin:-1rem -1rem 1rem -1rem;
    display:flex;align-items:center;justify-content:space-between;">
        <div style="font-weight:800;font-size:1.35rem;">{APP_NAME}</div>
        <div style="display:flex;align-items:center;gap:16px;">
            <div style="opacity:0.9;">{APP_VERSION}</div>
            <div style="background:#1e3a6b;border:none;color:white;font-weight:700;border-radius:8px;padding:6px 10px;">Suche</div>
        </div>
    </div>
    ''',
    unsafe_allow_html=True,
)

st.markdown('<div class="search-panel">', unsafe_allow_html=True)
with st.form("athlete_search_form", clear_on_submit=False):
    input_col, button_col = st.columns([4, 1])
    with input_col:
        search_query = st.text_input(
            "Athletensuche",
            value=st.session_state.search_query,
            placeholder="Name oder FIS-Code eingeben",
            label_visibility="collapsed",
        )
    with button_col:
        search_button = st.form_submit_button("Suchen")
st.markdown('</div>', unsafe_allow_html=True)

st.session_state.search_query = search_query

if search_button:
    cleaned_query = search_query.strip()
    if not cleaned_query:
        st.warning("Bitte gib einen Athletennamen oder einen FIS-Code ein.")
    else:
        with st.spinner("Athleten werden gesucht ..."):
            st.session_state.results = search_athletes(cleaned_query)
            st.session_state.selected_index = 0
            st.session_state.last_query = cleaned_query
        if not st.session_state.results:
            st.warning("Kein passender Alpine-Athlet gefunden.")

results = st.session_state.results
selected_athlete = results[st.session_state.selected_index] if results else None

nav_col, main_col = st.columns([0.9, 2.4])

with nav_col:
    st.markdown('<div class="content-title">Navigation</div>', unsafe_allow_html=True)
    st.session_state.active_view = st.radio(
        "Bereich",
        ["Athletendaten", "Rennauswertung", "FIS-Punkte", "Ergebnisse"],
        label_visibility="collapsed",
    )
    st.markdown('<div class="nav-caption">Die Athletensuche liegt wieder oberhalb der Navigation und ist direkt nutzbar.</div>', unsafe_allow_html=True)
    st.markdown('<div class="content-title" style="margin-top:1rem;">Trefferliste</div>', unsafe_allow_html=True)
    if not results:
        hint = "Noch keine Treffer. Suche oben nach einem Athleten."
        if st.session_state.last_query:
            hint = f'Keine Treffer für „{st.session_state.last_query}“. Bitte anderen Namen oder FIS-Code testen.'
        st.info(hint)
    else:
        labels = [f"{a['name']} | {a['nation_code']} | FIS-Code: {a['fis_code']}" for a in results]
        idx = st.radio(
            "Treffer auswählen",
            options=list(range(len(labels))),
            format_func=lambda i: labels[i],
            index=min(st.session_state.selected_index, len(labels) - 1),
            label_visibility="collapsed",
        )
        st.session_state.selected_index = idx
        selected_athlete = results[idx]

with main_col:
    if st.session_state.active_view == "Athletendaten":
        st.markdown('<div class="content-title">Athletendaten</div>', unsafe_allow_html=True)
        if not selected_athlete:
            st.info("Sobald ein Athlet gefunden wird, erscheinen hier die Athletendaten.")
        else:
            hero = (
                '<div class="hero-card">'
                f'<div class="hero-name">{selected_athlete["name"]}</div>'
                f'<div class="hero-meta">{selected_athlete["nation_flag"]} {selected_athlete["nation_name"]} | FIS-Code {selected_athlete["fis_code"]} | Competitor ID {selected_athlete["competitor_id"]}</div>'
                '</div>'
            )
            st.markdown(hero, unsafe_allow_html=True)
            row1 = st.columns(4)
            summary = [
                ("Nachname", selected_athlete["last_name"]),
                ("Vorname", selected_athlete["first_name"]),
                ("Geburtsdatum", selected_athlete["birthdate"]),
                ("Alter", selected_athlete["age"]),
            ]
            for col, (label, value) in zip(row1, summary):
                with col:
                    kpi_card(label, value)
            row2 = st.columns(4)
            details = [
                ("Nation", f'{selected_athlete["nation_flag"]} {selected_athlete["nation_name"]}'.strip()),
                ("Nationencode", selected_athlete["nation_code"]),
                ("Geschlecht", selected_athlete["gender"]),
                ("Verein", selected_athlete["club"]),
            ]
            for col, (label, value) in zip(row2, details):
                with col:
                    metric_card(label, value)
            st.link_button("Offizielles FIS-Profil öffnen", selected_athlete["url"])

    elif st.session_state.active_view == "Rennauswertung":
        st.markdown('<div class="content-title">Rennauswertung</div>', unsafe_allow_html=True)
        if not selected_athlete:
            st.info("Suche zuerst einen Athleten.")
        else:
            st.markdown('<div class="panel-note">Dieses Modul ist als klarer Platzhalter für die spätere Rennauswertung vorbereitet.</div>', unsafe_allow_html=True)

    elif st.session_state.active_view == "FIS-Punkte":
        st.markdown('<div class="content-title">FIS-Punkte</div>', unsafe_allow_html=True)
        if not selected_athlete:
            st.info("Suche zuerst einen Athleten.")
        else:
            st.markdown('<div class="panel-note">Dieser Bereich ist für die spätere FIS-Punkte-Analyse vorbereitet.</div>', unsafe_allow_html=True)

    elif st.session_state.active_view == "Ergebnisse":
        st.markdown('<div class="content-title">Ergebnisse</div>', unsafe_allow_html=True)
        if not selected_athlete:
            st.info("Suche zuerst einen Athleten.")
        else:
            st.markdown(
                f'<div class="mini-card"><strong>{selected_athlete["name"]}</strong><br>{selected_athlete["nation_flag"]} {selected_athlete["nation_name"]} | FIS-Code {selected_athlete["fis_code"]}</div>',
                unsafe_allow_html=True,
            )
            try:
                results_df = fetch_result_entries(selected_athlete["url"])
            except Exception as exc:
                results_df = None
                st.warning(f"Ergebnisse konnten nicht geladen werden: {exc}")

            if results_df is None or results_df.empty:
                st.info("Auf der Ergebnisseite konnten keine auslesbaren Resultate gefunden werden.")
            else:
                seasons = results_df["Saison"].dropna().astype(str).unique().tolist()
                seasons = sorted(seasons, reverse=True)
                season_options = ["Gesamtstatistik"] + seasons
                selected_season = st.selectbox("Saison wählen", season_options)

                filtered_df = results_df.copy()
                if selected_season != "Gesamtstatistik":
                    filtered_df = filtered_df[filtered_df["Saison"].astype(str) == selected_season].copy()

                summary = summarize_results(filtered_df)
                s1, s2, s3, s4 = st.columns(4)
                with s1:
                    kpi_card("Starts", summary["starts"])
                with s2:
                    kpi_card("Top 10", summary["top10"])
                with s3:
                    kpi_card("Beste Platzierung", summary["best"])
                with s4:
                    kpi_card("Disziplinen", summary["disciplines"])

                st.markdown('<div class="panel-note">Alle erkannten Disziplinen werden berücksichtigt. Die Resultate sind exakt chronologisch sortiert: neuestes Rennen zuerst.</div>', unsafe_allow_html=True)

                discipline_summary = starts_by_discipline(filtered_df)
                col_a, col_b = st.columns([1, 2])
                with col_a:
                    st.markdown("**Starts pro Disziplin**")
                    st.dataframe(discipline_summary, use_container_width=True, hide_index=True)
                with col_b:
                    st.markdown("**Chronologische Ergebnisliste**")
                    display_cols = [c for c in ["Datum", "Saison", "Disziplin", "Kategorie", "Nation", "Position", "FIS-Punkte", "Cup-Punkte"] if c in filtered_df.columns]
                    chron_df = filtered_df.sort_values("SortDate", ascending=False).copy()
                    st.dataframe(chron_df[display_cols], use_container_width=True, hide_index=True)

                st.link_button("Offizielle FIS-Ergebnisseite öffnen", results_url_from_profile(selected_athlete["url"]))

st.markdown('<div class="footer-note">v5.1 repariert die Athletensuche wieder vollständig und behält den verbesserten Ergebnisse-Parser bei.</div>', unsafe_allow_html=True)
