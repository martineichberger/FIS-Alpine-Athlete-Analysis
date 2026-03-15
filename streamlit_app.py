import html
import re
from urllib.parse import urlencode, quote_plus

import requests
import streamlit as st

APP_NAME = "FIS-Alpine-Athlete-Analysis"
APP_VERSION = "v2.0-streamlit"
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
        .app-title {
            font-size: 2rem;
            font-weight: 800;
            margin-bottom: 0.15rem;
        }
        .subtle {
            color: #94a3b8;
            margin-bottom: 1rem;
        }
        .card {
            padding: 1rem;
            border: 1px solid #243245;
            border-radius: 16px;
            background: #0f172a;
            margin-bottom: 0.8rem;
        }
        .label {
            color: #94a3b8;
            font-size: 0.82rem;
            margin-bottom: 0.2rem;
        }
        .value {
            font-size: 1.05rem;
            font-weight: 700;
        }
        .result-box {
            border: 1px solid #243245;
            border-radius: 14px;
            padding: 0.9rem;
            background: #0f172a;
            margin-bottom: 0.6rem;
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


@st.cache_data(show_spinner=False, ttl=1800)
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

    seen = []
    for url in urls:
        if url not in seen:
            seen.append(url)
    return seen


def extract_profile_links_from_search_page(page: str):
    matches = re.findall(r'href="([^"]*athlete-biography\.html[^"]+)"', page, flags=re.IGNORECASE)
    results = []
    for href in matches:
        href = html.unescape(href).replace("&amp;", "&")
        if href.startswith("/"):
            href = FIS_PROFILE_PREFIX + href
        elif href.startswith("http"):
            pass
        else:
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


def extract_value_from_text(text: str, label: str):
    pattern = rf"{re.escape(label)}\s*:?\s*(.{{0,90}}?)(?=\s+[A-Z][A-Za-z\- ]{{2,25}}\s*:|\s+[A-Z][a-z]+\s+[A-Z][A-Za-z]+\s*:|$)"
    match = re.search(pattern, text, re.IGNORECASE)
    if not match:
        return "-"
    value = match.group(1).strip(" :-")
    value = re.sub(r"\s+", " ", value)
    if not value or len(value) > 70:
        return "-"
    return value


def extract_age(text: str):
    match = re.search(r"Age\s*:?\s*(\d{1,2})", text, re.IGNORECASE)
    return match.group(1) if match else "-"


def score_athlete(athlete: dict, query: str, is_code: bool):
    score = 0
    if is_code:
        if athlete.get("fis_code") == query:
            score += 100
        if query in athlete.get("url", ""):
            score += 20
        return score

    q = normalize_name(query)
    name = normalize_name(athlete.get("name", ""))
    parts = [p for p in q.split(" ") if p]

    if q == name:
        score += 100
    if q in name:
        score += 60
    if all(p in name for p in parts):
        score += 40
    if name.startswith(parts[-1] if parts else q):
        score += 10
    return score


@st.cache_data(show_spinner=False, ttl=1800)
def fetch_athlete_profile(url: str, query: str, is_code: bool):
    session = get_session()
    response = session.get(url, timeout=TIMEOUT)
    response.raise_for_status()
    page = response.text
    clean_page = clean_html(page)

    title_match = re.search(r"<h1[^>]*>(.*?)</h1>", page, re.IGNORECASE | re.DOTALL)
    page_title = clean_html(title_match.group(1)) if title_match else "Unbekannter Athlet"

    fis_code = extract_value_from_text(clean_page, "FIS Code")
    nation = extract_value_from_text(clean_page, "Nation")
    birthdate = extract_value_from_text(clean_page, "Birthdate")
    age = extract_age(clean_page)
    club = extract_value_from_text(clean_page, "Club")
    place_of_birth = extract_value_from_text(clean_page, "Birth Place")
    residence = extract_value_from_text(clean_page, "Residence")
    status = extract_value_from_text(clean_page, "Status")
    gender = extract_value_from_text(clean_page, "Gender")
    skis = extract_value_from_text(clean_page, "Skis")
    boots = extract_value_from_text(clean_page, "Boots")
    poles = extract_value_from_text(clean_page, "Poles")
    helmet = extract_value_from_text(clean_page, "Helmet")
    goggles = extract_value_from_text(clean_page, "Goggles")
    gloves = extract_value_from_text(clean_page, "Gloves")
    racing_suit = extract_value_from_text(clean_page, "Racing suit")

    competitor_match = re.search(r"competitorid=(\d+)", url, re.IGNORECASE)
    competitor_id = competitor_match.group(1) if competitor_match else "-"

    athlete = {
        "name": page_title,
        "fis_code": fis_code or "-",
        "nation": nation or "-",
        "birthdate": birthdate or "-",
        "age": age or "-",
        "club": club or "-",
        "place_of_birth": place_of_birth or "-",
        "residence": residence or "-",
        "status": status or "-",
        "gender": gender or "-",
        "skis": skis or "-",
        "boots": boots or "-",
        "poles": poles or "-",
        "helmet": helmet or "-",
        "goggles": goggles or "-",
        "gloves": gloves or "-",
        "racing_suit": racing_suit or "-",
        "competitor_id": competitor_id,
        "url": url,
    }

    athlete["score"] = score_athlete(athlete, query, is_code)
    return athlete


@st.cache_data(show_spinner=True, ttl=900)
def search_athletes(query: str):
    query = " ".join(query.split())
    is_code = query.isdigit()
    session = get_session()
    profile_links = []

    for url in build_fis_search_urls(query):
        response = session.get(url, timeout=TIMEOUT)
        response.raise_for_status()
        profile_links.extend(extract_profile_links_from_search_page(response.text))

    if not profile_links:
        ddg_query = (
            'site:fis-ski.com/DB/general/athlete-biography.html '
            '"sectorcode=AL" '
            f'"{query}"'
        )
        response = session.get(
            DUCKDUCKGO_HTML,
            params={"q": ddg_query},
            timeout=TIMEOUT,
        )
        response.raise_for_status()
        profile_links.extend(extract_profile_links_duckduckgo(response.text))

    unique_links = []
    for link in profile_links:
        if link not in unique_links:
            unique_links.append(link)

    athletes = []
    seen_keys = set()
    for link in unique_links[:25]:
        try:
            athlete = fetch_athlete_profile(link, query, is_code)
        except Exception:
            continue

        unique_key = (
            athlete.get("name", "").strip().lower(),
            athlete.get("fis_code", "").strip(),
            athlete.get("competitor_id", "").strip(),
        )
        if unique_key in seen_keys:
            continue
        seen_keys.add(unique_key)
        athletes.append(athlete)

    athletes.sort(key=lambda a: a.get("score", 0), reverse=True)

    if is_code:
        exact = [a for a in athletes if a.get("fis_code") == query]
        if exact:
            return exact

    return athletes[:12]


def metric_card(label: str, value: str):
    st.markdown(
        f'<div class="card"><div class="label">{label}</div><div class="value">{value}</div></div>',
        unsafe_allow_html=True,
    )


if "search_results" not in st.session_state:
    st.session_state.search_results = []
if "selected_index" not in st.session_state:
    st.session_state.selected_index = 0

left, mid, right = st.columns([1.1, 2.1, 0.7])
with left:
    st.text_input("Suche", key="search_query", placeholder="z. B. Stefan Eichberger oder 54609")
with mid:
    st.markdown(f'<div class="app-title">{APP_NAME}</div>', unsafe_allow_html=True)
with right:
    st.markdown(
        f'<div style="text-align:right; padding-top:0.55rem;">{APP_VERSION}</div>',
        unsafe_allow_html=True,
    )

st.markdown(
    '<div class="subtle">Direkte FIS-Suche für Alpine-Athleten mit robusterem Matching und Ergebnisliste.</div>',
    unsafe_allow_html=True,
)

search_col, reset_col = st.columns([1, 0.22])
with search_col:
    run_search = st.button("Athlet suchen", use_container_width=True)
with reset_col:
    reset = st.button("Reset", use_container_width=True)

if reset:
    st.session_state.search_results = []
    st.session_state.selected_index = 0
    st.rerun()

query = st.session_state.search_query.strip() if st.session_state.search_query else ""

if run_search:
    if not query:
        st.warning("Bitte gib einen Athletennamen oder einen FIS-Code ein.")
    else:
        try:
            results = search_athletes(query)
            st.session_state.search_results = results
            st.session_state.selected_index = 0
            if not results:
                st.warning("Kein passender Alpine-Athlet gefunden.")
        except Exception as exc:
            st.error(f"Suche fehlgeschlagen: {exc}")

left_col, right_col = st.columns([1, 2])

with left_col:
    st.subheader("Trefferliste")
    if not st.session_state.search_results:
        st.info("Noch keine Treffer. Suche oben nach Name oder FIS-Code.")
    else:
        labels = [
            f"{a['name']} | {a['nation']} | FIS-Code: {a['fis_code']}"
            for a in st.session_state.search_results
        ]
        selected = st.radio(
            "Athlet auswählen",
            options=list(range(len(labels))),
            format_func=lambda i: labels[i],
            index=min(st.session_state.selected_index, len(labels) - 1),
            label_visibility="collapsed",
        )
        st.session_state.selected_index = selected

        selected_athlete = st.session_state.search_results[selected]
        st.markdown(
            f"""
            <div class="result-box">
                <strong>Aktuelle Auswahl</strong><br>
                {selected_athlete['name']}<br>
                {selected_athlete['nation']} · FIS-Code {selected_athlete['fis_code']}
            </div>
            """,
            unsafe_allow_html=True,
        )

with right_col:
    st.subheader("Athletenprofil")
    if not st.session_state.search_results:
        st.info("Sobald du suchst, erscheint hier das Athletenprofil.")
    else:
        athlete = st.session_state.search_results[st.session_state.selected_index]
        st.markdown(f"### {athlete['name']}")
        action_cols = st.columns([1, 1, 2])
        with action_cols[0]:
            st.link_button("FIS-Profil öffnen", athlete["url"], use_container_width=True)
        with action_cols[1]:
            st.link_button(
                "FIS-Suche öffnen",
                f"{FIS_SEARCH_URL}?{urlencode({'sectorcode': 'AL', 'search': 'true', 'lastname': athlete['name'].split()[-1], 'firstname': ' '.join(athlete['name'].split()[:-1]), 'fiscode': '', 'birthyear': '', 'gendercode': '', 'nationcode': '', 'skiclub': '', 'skis': '', 'status': ''})}",
                use_container_width=True,
            )

        rows = [
            [("Nation", athlete["nation"]), ("FIS-Code", athlete["fis_code"]), ("Competitor ID", athlete["competitor_id"])],
            [("Status", athlete["status"]), ("Geschlecht", athlete["gender"]), ("Alter", athlete["age"])],
            [("Geburtsdatum", athlete["birthdate"]), ("Club", athlete["club"]), ("Wohnort", athlete["residence"])],
            [("Geburtsort", athlete["place_of_birth"]), ("Skis", athlete["skis"]), ("Boots", athlete["boots"])],
            [("Poles", athlete["poles"]), ("Helmet", athlete["helmet"]), ("Goggles", athlete["goggles"])],
            [("Gloves", athlete["gloves"]), ("Racing Suit", athlete["racing_suit"]), ("URL", athlete["url"])],
        ]

        for row in rows:
            cols = st.columns(3)
            for col, (label, value) in zip(cols, row):
                with col:
                    metric_card(label, value)

        st.markdown("#### Kurzprofil")
        st.text(
            f"Athlet: {athlete['name']}\n"
            f"Nation: {athlete['nation']}\n"
            f"FIS-Code: {athlete['fis_code']}\n"
            f"Competitor ID: {athlete['competitor_id']}\n"
            f"Status: {athlete['status']}\n"
            f"Geschlecht: {athlete['gender']}\n"
            f"Geburtsdatum: {athlete['birthdate']}\n"
            f"Alter: {athlete['age']}\n"
            f"Club: {athlete['club']}\n"
            f"Wohnort: {athlete['residence']}"
        )
