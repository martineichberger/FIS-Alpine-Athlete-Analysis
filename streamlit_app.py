import hashlib
import html
import json
import re
import time
from datetime import datetime
from pathlib import Path
from urllib.parse import urlencode, urljoin, urlparse, parse_qsl, urlunparse

import pandas as pd
import requests
import streamlit as st

APP_NAME = "FIS-Alpine-Athlete-Analysis"
APP_VERSION = "v5.8-results-display-refresh"
USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/122.0.0.0 Safari/537.36"
)
TIMEOUT = 25
FIS_SEARCH_URL = "https://www.fis-ski.com/DB/general/biographies.html"
FIS_PROFILE_PREFIX = "https://www.fis-ski.com"
DUCKDUCKGO_HTML = "https://html.duckduckgo.com/html/"
CACHE_DIR = Path(".cache/fis_app")
SEARCH_CACHE_TTL = 60 * 60 * 6
PROFILE_CACHE_TTL = 60 * 60 * 24
RESULTS_CACHE_TTL = 60 * 60 * 12
HTTP_CACHE_TTL = 60 * 60 * 6

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


def ensure_cache_dir() -> None:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)


def cache_path(namespace: str, key: str) -> Path:
    digest = hashlib.sha256(key.encode("utf-8")).hexdigest()
    return CACHE_DIR / f"{namespace}_{digest}.json"


def load_cache(namespace: str, key: str, ttl_seconds: int):
    ensure_cache_dir()
    path = cache_path(namespace, key)
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        created_at = float(payload.get("created_at", 0))
        if time.time() - created_at > ttl_seconds:
            return None
        return payload.get("data")
    except Exception:
        return None


def save_cache(namespace: str, key: str, data):
    ensure_cache_dir()
    path = cache_path(namespace, key)
    payload = {"created_at": time.time(), "data": data}
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")


def clear_cache_files():
    ensure_cache_dir()
    for file_path in CACHE_DIR.glob("*.json"):
        try:
            file_path.unlink()
        except Exception:
            pass


def get_text_with_cache(url: str, ttl_seconds: int = HTTP_CACHE_TTL, params: dict | None = None) -> str:
    cache_key = json.dumps({"url": url, "params": params or {}}, sort_keys=True)
    cached = load_cache("http", cache_key, ttl_seconds)
    if cached:
        return cached
    session = get_session()
    response = session.get(url, params=params, timeout=TIMEOUT)
    response.raise_for_status()
    text = response.text
    save_cache("http", cache_key, text)
    return text


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


def extract_fis_code(page: str, clean_page: str, url: str = "") -> str:
    patterns = [
        r"FIS\s*Code\s*:?\s*(-?\d{3,10})\b",
        r'"fisCode"\s*:\s*"?(-?\d{3,10})"?',
        r"fiscode=([-?\d]{3,10})\b",
    ]
    for source in (page, clean_page, url):
        for pattern in patterns:
            match = re.search(pattern, source, re.IGNORECASE)
            if match:
                value = match.group(1).strip().lstrip("?")
                if value:
                    return value
    fallback = extract_value(clean_page, "FIS Code")
    return fallback if fallback and fallback != "-" else "-"


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
        return code_match.group(1).strip(), code_match.group(2).strip()
    text_match = re.search(r"\b([A-Z]{3})\s+([A-Z][a-zA-Z\-]+(?:\s+[A-Z][a-zA-Z\-]+)?)\b", clean_page)
    if text_match:
        return text_match.group(1).strip(), text_match.group(2).strip()
    nation_label = extract_value(clean_page, "Nation")
    if nation_label and nation_label != "-":
        parts = nation_label.split(" ", 1)
        if len(parts) == 2 and len(parts[0]) == 3 and parts[0].isalpha():
            return parts[0].upper(), parts[1].strip()
        return "-", nation_label.strip()
    return "-", "-"


def fetch_profile(url: str):
    cached = load_cache("profile", url, PROFILE_CACHE_TTL)
    if cached:
        return cached

    page = get_text_with_cache(url, ttl_seconds=PROFILE_CACHE_TTL)
    title_match = re.search(r"<h1[^>]*>(.*?)</h1>", page, re.IGNORECASE | re.DOTALL)
    raw_name = clean_html(title_match.group(1)) if title_match else "Unbekannter Athlet"
    last_name, first_name = split_name(raw_name)
    clean_page = clean_html(page)
    competitor_match = re.search(r"competitorid=(\d+)", url, re.IGNORECASE)
    competitor_id = competitor_match.group(1) if competitor_match else "-"
    nation_code, nation_name = extract_nation_from_page(page, clean_page)
    club = extract_value(clean_page, "Club")
    if club == "-":
        club_match = re.search(r"</h1>\s*([^<]{3,120})<", page, re.IGNORECASE | re.DOTALL)
        if club_match:
            club_candidate = clean_html(club_match.group(1))
            if club_candidate and len(club_candidate) <= 80:
                club = club_candidate

    athlete = {
        "name": raw_name,
        "last_name": last_name,
        "first_name": first_name,
        "nation_code": nation_code,
        "nation_name": nation_name,
        "nation_flag": country_code_to_flag(nation_code),
        "birthdate": extract_value(clean_page, "Birthdate"),
        "age": extract_age(clean_page),
        "club": club,
        "gender": extract_value(clean_page, "Gender"),
        "fis_code": extract_fis_code(page, clean_page, url),
        "status": extract_value(clean_page, "Status"),
        "competitor_id": competitor_id,
        "url": url,
    }
    save_cache("profile", url, athlete)
    return athlete


def search_athletes(query: str):
    query = " ".join(query.split())
    if not query:
        return []

    cached = load_cache("search", query.lower(), SEARCH_CACHE_TTL)
    if cached is not None:
        return cached

    profile_links = []
    for url in build_fis_search_urls(query):
        try:
            page = get_text_with_cache(url, ttl_seconds=SEARCH_CACHE_TTL)
            profile_links.extend(extract_profile_links_from_search_page(page))
        except Exception:
            pass

    if not profile_links:
        try:
            ddg_query = (
                'site:fis-ski.com/DB/general/athlete-biography.html '
                '"sectorcode=AL" '
                f'"{query}"'
            )
            ddg_page = get_text_with_cache(DUCKDUCKGO_HTML, ttl_seconds=SEARCH_CACHE_TTL, params={"q": ddg_query})
            profile_links.extend(extract_profile_links_duckduckgo(ddg_page))
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
            athletes = exact[:12]
        else:
            athletes = athletes[:12]
    else:
        athletes = athletes[:12]

    save_cache("search", query.lower(), athletes)
    return athletes


def results_url_from_profile(athlete_url: str) -> str:
    if "type=result" in athlete_url:
        return athlete_url
    if "?" in athlete_url:
        return athlete_url + "&type=result"
    return athlete_url + "?type=result"


RESULTS_CACHE_NAMESPACE = "results_v2"


def update_url_query(url: str, updates: dict) -> str:
    parsed = urlparse(url)
    query = dict(parse_qsl(parsed.query, keep_blank_values=True))
    for key, value in updates.items():
        if value is None:
            query.pop(key, None)
        else:
            query[key] = str(value)
    new_query = urlencode(query, doseq=True)
    return urlunparse(parsed._replace(query=new_query))


def normalize_result_url(url: str, base_url: str = "") -> str:
    candidate = html.unescape((url or "").replace("\\/", "/").replace("&amp;", "&")).strip(' "\'')
    if not candidate:
        return ""

    if candidate.startswith("//"):
        candidate = "https:" + candidate
    elif candidate.startswith("/"):
        candidate = urljoin(FIS_PROFILE_PREFIX, candidate)
    elif not candidate.startswith("http"):
        candidate = urljoin(base_url or FIS_PROFILE_PREFIX, candidate)

    if "athlete-biography.html" not in candidate:
        return ""
    if "type=result" not in candidate.lower():
        candidate = update_url_query(candidate, {"type": "result"})
    return candidate


def extract_result_page_links(page: str, base_url: str):
    discovered = []

    href_matches = re.findall(r'href="([^"]+)"', page, flags=re.IGNORECASE)
    href_matches += re.findall(r"href='([^']+)'", page, flags=re.IGNORECASE)
    href_matches += re.findall(r'"(https?:[^"]*athlete-biography\.html[^"]*)"', page, flags=re.IGNORECASE)
    href_matches += re.findall(r'"([^"]*athlete-biography\.html[^"]*)"', page, flags=re.IGNORECASE)

    for raw in href_matches:
        normalized = normalize_result_url(raw, base_url=base_url)
        if normalized:
            discovered.append(normalized)

    return list(dict.fromkeys(discovered))


def build_pagination_candidates(base_url: str):
    candidates = []

    for limit in (50, 100, 200, 500, 1000):
        candidates.append(update_url_query(base_url, {"limit": limit}))

    for limit in (50, 100, 200):
        for offset in range(limit, 1201, limit):
            candidates.append(update_url_query(base_url, {"limit": limit, "offset": offset}))
            candidates.append(update_url_query(base_url, {"limit": limit, "start": offset}))

    for limit in (50, 100, 200):
        for page_no in range(2, 16):
            candidates.append(update_url_query(base_url, {"limit": limit, "page": page_no}))
            candidates.append(update_url_query(base_url, {"limit": limit, "pageNum": page_no}))
            candidates.append(update_url_query(base_url, {"limit": limit, "pageNo": page_no}))

    return list(dict.fromkeys(candidates))


def merge_result_entries(existing: dict, candidates):
    added = 0
    for candidate in candidates:
        parsed = parse_result_line(candidate)
        if not parsed:
            continue
        key = (
            parsed["Datum"],
            parsed["Disziplin"],
            parsed["Position"],
            parsed["Nation"],
            parsed["Rennort"],
            parsed["Kategorie"],
            parsed["Raw"][:180],
        )
        if key in existing:
            continue
        existing[key] = parsed
        added += 1
    return added


def compute_season(date_str: str):
    try:
        dt = datetime.strptime(date_str, "%d-%m-%Y")
    except Exception:
        return None
    return dt.year + 1 if dt.month >= 7 else dt.year


def extract_discipline(text: str):
    matches = []
    for d in sorted(DISCIPLINES, key=len, reverse=True):
        for match in re.finditer(rf"\b{re.escape(d)}\b", text, flags=re.IGNORECASE):
            matches.append(
                {
                    "discipline": d,
                    "start": match.start(),
                    "end": match.end(),
                    "length": len(d),
                }
            )

    if not matches:
        return None, -1

    filtered = []
    for candidate in matches:
        enclosed_by_longer = any(
            other["length"] > candidate["length"]
            and other["start"] <= candidate["start"]
            and other["end"] >= candidate["end"]
            for other in matches
        )
        if not enclosed_by_longer:
            filtered.append(candidate)

    best = max(filtered, key=lambda item: (item["start"], item["length"]))
    return best["discipline"], best["start"]


def extract_location(before_disc: str, category: str, nation: str) -> str:
    cleaned = before_disc.strip()

    if nation and nation != "-":
        cleaned = re.sub(rf"\b{re.escape(nation)}\b", " ", cleaned)

    if category and category != "-":
        cleaned = re.sub(re.escape(category), " ", cleaned, flags=re.IGNORECASE)

    cleaned = re.sub(r"\b\d{1,2}\b", " ", cleaned)
    cleaned = re.sub(r"\s*[|,/\-]\s*", " ", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned).strip(" -|,;/")

    return cleaned if cleaned else "-"


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

    position = tokens[0] if tokens else "-"
    fis_points = "-"
    cup_points = "-"
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
    before_disc = text[10:discipline_pos].strip()
    code_matches = list(re.finditer(r"\b([A-Z]{3})\b", before_disc))
    if code_matches:
        nation = code_matches[-1].group(1)
    else:
        fallback_codes = re.findall(r"\b([A-Z]{3})\b", text[10:])
        if fallback_codes:
            nation = fallback_codes[0]

    location = extract_location(before_disc, category, nation)
    season = compute_season(date_str)

    return {
        "Datum": date_str,
        "Saison": season if season is not None else "-",
        "Disziplin": discipline,
        "Kategorie": category,
        "Rennort": location,
        "Nation": nation,
        "Position": position,
        "FIS-Punkte": fis_points,
        "Cup-Punkte": cup_points,
        "Raw": text,
    }



def extract_result_candidates_from_text(source_text: str):
    if not source_text:
        return []

    normalized = re.sub(r"\s+", " ", source_text).strip()
    if not normalized:
        return []

    candidates = []

    date_positions = [m.start() for m in re.finditer(r"\d{2}-\d{2}-\d{4}", normalized)]
    for i, start in enumerate(date_positions):
        end = date_positions[i + 1] if i + 1 < len(date_positions) else min(len(normalized), start + 220)
        chunk = normalized[start:end].strip(" |,;")
        if chunk:
            candidates.append(chunk)

    for match in re.finditer(r"\d{2}-\d{2}-\d{4}", normalized):
        chunk = normalized[match.start(): match.start() + 220].strip(" |,;")
        if chunk:
            candidates.append(chunk)

    return candidates


def extract_result_candidates_from_page(page: str):
    candidates = []

    anchors = re.findall(r"<a[^>]*>(.*?)</a>", page, flags=re.IGNORECASE | re.DOTALL)
    candidates.extend(clean_html(a) for a in anchors)

    blocks = re.findall(r">(.*?)<", page, flags=re.IGNORECASE | re.DOTALL)
    candidates.extend(clean_html(b) for b in blocks if re.search(r"\d{2}-\d{2}-\d{4}", clean_html(b)))

    script_blocks = re.findall(r"<script[^>]*>(.*?)</script>", page, flags=re.IGNORECASE | re.DOTALL)
    for block in script_blocks:
        if re.search(r"\d{2}-\d{2}-\d{4}", block):
            candidates.extend(extract_result_candidates_from_text(html.unescape(block)))

    cleaned_page = clean_html(page)
    candidates.extend(extract_result_candidates_from_text(cleaned_page))

    unescaped_page = html.unescape(page)
    if re.search(r"\d{2}-\d{2}-\d{4}", unescaped_page):
        candidates.extend(extract_result_candidates_from_text(clean_html(unescaped_page)))
        candidates.extend(extract_result_candidates_from_text(unescaped_page))

    deduped = []
    seen = set()
    for item in candidates:
        item = re.sub(r"\s+", " ", str(item)).strip()
        if len(item) < 18 or not re.search(r"\d{2}-\d{2}-\d{4}", item):
            continue
        key = item[:220]
        if key in seen:
            continue
        seen.add(key)
        deduped.append(item)
    return deduped


def fetch_result_entries(athlete_url: str):
    cache_key = results_url_from_profile(athlete_url)
    cached = load_cache(RESULTS_CACHE_NAMESPACE, cache_key, RESULTS_CACHE_TTL)
    if cached:
        df = pd.DataFrame(cached)
        if not df.empty and "Datum" in df.columns:
            df["SortDate"] = pd.to_datetime(df["Datum"], format="%d-%m-%Y", errors="coerce")
        return df

    base_url = results_url_from_profile(athlete_url)
    pages_to_try = []
    seen_urls = set()

    def queue(url: str):
        normalized = normalize_result_url(url, base_url=base_url)
        if normalized and normalized not in seen_urls:
            seen_urls.add(normalized)
            pages_to_try.append(normalized)

    queue(base_url)

    entries_by_key = {}
    processed_pages = 0
    show_more_detected = False

    while pages_to_try and processed_pages < 60:
        current_url = pages_to_try.pop(0)
        try:
            page = get_text_with_cache(current_url, ttl_seconds=RESULTS_CACHE_TTL)
        except Exception:
            continue

        processed_pages += 1
        page_lower = page.lower()
        if "show more" in page_lower or "showmore" in page_lower:
            show_more_detected = True

        merge_result_entries(entries_by_key, extract_result_candidates_from_page(page))

        for discovered_url in extract_result_page_links(page, current_url):
            queue(discovered_url)

        if processed_pages == 1 or show_more_detected:
            for candidate_url in build_pagination_candidates(base_url):
                queue(candidate_url)

    entries = list(entries_by_key.values())
    if not entries:
        return None

    df = pd.DataFrame(entries)
    df["SortDate"] = pd.to_datetime(df["Datum"], format="%d-%m-%Y", errors="coerce")
    df = (
        df.sort_values(
            ["SortDate", "Disziplin", "Kategorie", "Rennort"],
            ascending=[False, True, True, True],
        )
        .drop_duplicates(
            subset=["Datum", "Disziplin", "Kategorie", "Rennort", "Nation", "Position"],
            keep="first",
        )
        .reset_index(drop=True)
    )
    save_cache(
        RESULTS_CACHE_NAMESPACE,
        cache_key,
        df.drop(columns=["SortDate"], errors="ignore").to_dict(orient="records"),
    )
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


def get_current_season() -> int:
    now = datetime.now()
    return now.year + 1 if now.month >= 7 else now.year


def status_rate(df: pd.DataFrame, status: str):
    if df is None or df.empty or "Position" not in df.columns:
        return 0, "0.0%"
    series = df["Position"].fillna("").astype(str).str.strip().str.upper()
    count = int((series == status.upper()).sum())
    rate = (count / len(df) * 100) if len(df) else 0
    return count, f"{rate:.1f}%"


def build_season_overview(df: pd.DataFrame, season: int):
    empty_summary = {
        "season": str(season),
        "starts": 0,
        "discipline_counts": pd.DataFrame(columns=["Disziplin", "Starts"]),
        "dnf_count": 0,
        "dnf_rate": "0.0%",
        "dsq_count": 0,
        "dsq_rate": "0.0%",
        "dns_count": 0,
        "dns_rate": "0.0%",
    }
    if df is None or df.empty or "Saison" not in df.columns:
        return empty_summary

    season_df = df[df["Saison"].astype(str) == str(season)].copy()
    if season_df.empty:
        return empty_summary

    dnf_count, dnf_rate = status_rate(season_df, "DNF")
    dsq_count, dsq_rate = status_rate(season_df, "DSQ")
    dns_count, dns_rate = status_rate(season_df, "DNS")

    return {
        "season": str(season),
        "starts": int(len(season_df)),
        "discipline_counts": starts_by_discipline(season_df),
        "dnf_count": dnf_count,
        "dnf_rate": dnf_rate,
        "dsq_count": dsq_count,
        "dsq_rate": dsq_rate,
        "dns_count": dns_count,
        "dns_rate": dns_rate,
    }


def classify_result_status(position_value) -> str:
    value = str(position_value or "").strip().upper()
    if not value or value == "-":
        return "Unklar"
    if value in {"DNF", "DSQ", "DNS"}:
        return value
    if value in {"DNQ", "DNP", "DIS", "NPS"}:
        return value
    return "Gewertet" if value.isdigit() else value


def build_result_display_df(df: pd.DataFrame) -> pd.DataFrame:
    if df is None or df.empty:
        return pd.DataFrame(
            columns=[
                "Datum", "Saison", "Disziplin", "Kategorie", "Rennort",
                "Nation", "Position", "Status", "FIS-Punkte", "Cup-Punkte"
            ]
        )

    view_df = df.copy()
    view_df["Status"] = view_df["Position"].apply(classify_result_status)
    view_df["PlatzZahl"] = pd.to_numeric(view_df["Position"], errors="coerce")

    if "SortDate" not in view_df.columns and "Datum" in view_df.columns:
        view_df["SortDate"] = pd.to_datetime(view_df["Datum"], format="%d-%m-%Y", errors="coerce")

    return view_df


def summarize_result_statuses(df: pd.DataFrame) -> dict:
    if df is None or df.empty:
        return {
            "gewertet": "0",
            "podien": "0",
            "dnf": "0",
            "dsq_dns": "0",
        }

    work = build_result_display_df(df)
    numeric = pd.to_numeric(work["Position"], errors="coerce")

    gewertet = int(numeric.notna().sum())
    podien = int((numeric <= 3).sum()) if numeric.notna().any() else 0
    dnf = int((work["Status"] == "DNF").sum())
    dsq_dns = int(work["Status"].isin(["DSQ", "DNS"]).sum())

    return {
        "gewertet": str(gewertet),
        "podien": str(podien),
        "dnf": str(dnf),
        "dsq_dns": str(dsq_dns),
    }


def discipline_overview_table(df: pd.DataFrame) -> pd.DataFrame:
    if df is None or df.empty:
        return pd.DataFrame(columns=["Disziplin", "Starts", "Gewertet", "DNF", "DSQ", "DNS", "Beste Platzierung"])

    work = build_result_display_df(df)
    grouped = []
    for discipline, group in work.groupby("Disziplin", dropna=False):
        numeric = pd.to_numeric(group["Position"], errors="coerce")
        best = "-"
        if numeric.notna().any():
            best = str(int(numeric.min()))
        grouped.append(
            {
                "Disziplin": discipline,
                "Starts": int(len(group)),
                "Gewertet": int(numeric.notna().sum()),
                "DNF": int((group["Status"] == "DNF").sum()),
                "DSQ": int((group["Status"] == "DSQ").sum()),
                "DNS": int((group["Status"] == "DNS").sum()),
                "Beste Platzierung": best,
            }
        )

    return (
        pd.DataFrame(grouped)
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
            <div style="background:#1e3a6b;border:none;color:white;font-weight:700;border-radius:8px;padding:6px 10px;">Cache aktiv</div>
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
    st.markdown('<div class="nav-caption">Such- und Ergebnisdaten werden lokal im Ordner .cache/fis_app zwischengespeichert.</div>', unsafe_allow_html=True)
    if st.button("Cache leeren"):
        clear_cache_files()
        st.success("Lokaler Cache wurde geleert.")
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

            try:
                athlete_results_df = fetch_result_entries(selected_athlete["url"])
            except Exception as exc:
                athlete_results_df = None
                st.warning(f"Saisonüberblick konnte nicht geladen werden: {exc}")

            current_season = get_current_season()
            season_overview = build_season_overview(athlete_results_df, current_season)
            st.markdown(
                f'<div class="panel-note">Saisonüberblick der aktuellen Saison {season_overview["season"]}: Gesamtzahl der Rennen, Starts pro Disziplin sowie DNF-, DSQ- und DNS-Quoten.</div>',
                unsafe_allow_html=True,
            )

            o1, o2, o3, o4 = st.columns(4)
            with o1:
                kpi_card("Rennen aktuell", str(season_overview["starts"]))
            with o2:
                kpi_card("DNF-Quote", f'{season_overview["dnf_count"]} | {season_overview["dnf_rate"]}')
            with o3:
                kpi_card("DSQ-Quote", f'{season_overview["dsq_count"]} | {season_overview["dsq_rate"]}')
            with o4:
                kpi_card("DNS-Quote", f'{season_overview["dns_count"]} | {season_overview["dns_rate"]}')

            col_overview_a, col_overview_b = st.columns([1, 1])
            with col_overview_a:
                st.markdown(f"**Starts pro Disziplin | Saison {season_overview['season']}**")
                st.dataframe(season_overview["discipline_counts"], use_container_width=True, hide_index=True)
            with col_overview_b:
                if athlete_results_df is None or athlete_results_df.empty:
                    st.info("Für die aktuelle Saison konnten noch keine auslesbaren Ergebnisse geladen werden.")
                else:
                    season_df = athlete_results_df[athlete_results_df["Saison"].astype(str) == season_overview["season"]].copy()
                    display_cols = [c for c in ["Datum", "Disziplin", "Kategorie", "Rennort", "Nation", "Position"] if c in season_df.columns]
                    if season_df.empty:
                        st.info(f"Für die Saison {season_overview['season']} wurden aktuell keine Rennen gefunden.")
                    else:
                        st.markdown(f"**Letzte Rennen | Saison {season_overview['season']}**")
                        season_df = season_df.sort_values("SortDate", ascending=False)
                        st.dataframe(season_df[display_cols].head(12), use_container_width=True, hide_index=True)

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
                results_view_df = build_result_display_df(results_df)

                seasons = sorted(results_view_df["Saison"].dropna().astype(str).unique().tolist(), reverse=True)
                disciplines = sorted(results_view_df["Disziplin"].dropna().astype(str).unique().tolist())
                categories = sorted(results_view_df["Kategorie"].dropna().astype(str).unique().tolist())
                statuses = ["Alle Status", "Gewertet", "DNF", "DSQ", "DNS", "DNQ", "DNP", "DIS", "NPS", "Unklar"]

                f1, f2, f3, f4 = st.columns(4)
                with f1:
                    selected_season = st.selectbox("Saison", ["Alle Saisonen"] + seasons, key="results_season_filter")
                with f2:
                    selected_discipline = st.selectbox("Disziplin", ["Alle Disziplinen"] + disciplines, key="results_discipline_filter")
                with f3:
                    selected_category = st.selectbox("Kategorie", ["Alle Kategorien"] + categories, key="results_category_filter")
                with f4:
                    selected_status = st.selectbox("Status", statuses, key="results_status_filter")

                filtered_df = results_view_df.copy()
                if selected_season != "Alle Saisonen":
                    filtered_df = filtered_df[filtered_df["Saison"].astype(str) == selected_season].copy()
                if selected_discipline != "Alle Disziplinen":
                    filtered_df = filtered_df[filtered_df["Disziplin"].astype(str) == selected_discipline].copy()
                if selected_category != "Alle Kategorien":
                    filtered_df = filtered_df[filtered_df["Kategorie"].astype(str) == selected_category].copy()
                if selected_status != "Alle Status":
                    filtered_df = filtered_df[filtered_df["Status"].astype(str) == selected_status].copy()

                summary = summarize_results(filtered_df)
                status_summary = summarize_result_statuses(filtered_df)

                s1, s2, s3, s4 = st.columns(4)
                with s1:
                    kpi_card("Angezeigte Rennen", summary["starts"])
                with s2:
                    kpi_card("Gewertet", status_summary["gewertet"])
                with s3:
                    kpi_card("Podien", status_summary["podien"])
                with s4:
                    kpi_card("Beste Platzierung", summary["best"])

                s5, s6, s7, s8 = st.columns(4)
                with s5:
                    kpi_card("Top 10", summary["top10"])
                with s6:
                    kpi_card("DNF", status_summary["dnf"])
                with s7:
                    kpi_card("DSQ + DNS", status_summary["dsq_dns"])
                with s8:
                    kpi_card("Disziplinen", summary["disciplines"])

                st.markdown(
                    '<div class="panel-note">Die Ergebnisanzeige wurde überarbeitet: klare Filter, zusätzlicher Status je Rennen, bessere Übersicht nach Disziplin und eine bereinigte Ergebnisliste mit Datum, Ort, Kategorie und Punkten.</div>',
                    unsafe_allow_html=True,
                )

                tab_overview, tab_results, tab_disciplines = st.tabs(["Übersicht", "Ergebnisliste", "Disziplinen"])

                with tab_overview:
                    left, right = st.columns([1, 2])
                    with left:
                        st.markdown("**Starts pro Disziplin**")
                        st.dataframe(
                            starts_by_discipline(filtered_df),
                            use_container_width=True,
                            hide_index=True,
                        )
                    with right:
                        st.markdown("**Statusübersicht der gefilterten Rennen**")
                        status_df = pd.DataFrame(
                            [
                                {"Status": "Gewertet", "Anzahl": status_summary["gewertet"]},
                                {"Status": "DNF", "Anzahl": status_summary["dnf"]},
                                {"Status": "DSQ + DNS", "Anzahl": status_summary["dsq_dns"]},
                            ]
                        )
                        st.dataframe(status_df, use_container_width=True, hide_index=True)

                with tab_results:
                    display_cols = [
                        c for c in
                        ["Datum", "Saison", "Disziplin", "Kategorie", "Rennort", "Nation", "Position", "Status", "FIS-Punkte", "Cup-Punkte"]
                        if c in filtered_df.columns
                    ]
                    chron_df = (
                        filtered_df
                        .sort_values(["SortDate", "Disziplin", "Kategorie"], ascending=[False, True, True])
                        .copy()
                    )
                    st.dataframe(
                        chron_df[display_cols],
                        use_container_width=True,
                        hide_index=True,
                    )

                with tab_disciplines:
                    st.markdown("**Detailübersicht nach Disziplin**")
                    st.dataframe(
                        discipline_overview_table(filtered_df),
                        use_container_width=True,
                        hide_index=True,
                    )

                st.link_button("Offizielle FIS-Ergebnisseite öffnen", results_url_from_profile(selected_athlete["url"]))

st.markdown('<div class="footer-note">v5.8 überarbeitet die Ergebnisanzeige mit klareren Filtern, Status-Auswertung, Tabs für Übersicht und Ergebnisliste sowie einer deutlich besseren Disziplinenübersicht.</div>', unsafe_allow_html=True)
