import datetime
import json
from pathlib import Path
from urllib.parse import quote
import feedparser
import streamlit as st

MAX_TRIGGER_AGE_DAYS = 90

TRIGGER_WEIGHTS = {
    "funding": 3,
    "facility_expansion": 3,
    "acquisition": 3,
    "divestiture": 2,
    "partnership": 2,
    "vendor_contract": 3,
    "product_launch": 2,
    "regulatory_milestone": 3,
    "new_hire": 2,
    "general_press": 1,
}

# Additional keyword signals provided by user
# Grouped to contribute additive weights on top of base trigger type
KEYWORD_SIGNALS = {
    "high_intent": {
        "weight": 3,
        "keywords": [
            "expansion", "facility", "new site", "groundbreaking", "ribbon cutting",
            "capital investment", "manufacturing", "biomanufacturing", "scale-up",
            "capacity increase", "large-scale", "gmp", "tech transfer", "commissioning",
            "bioreactor", "single-use", "automation", "mes", "digital manufacturing",
        ],
    },
    "strategic_ops": {
        "weight": 2,
        "keywords": [
            "partnership", "collaboration", "agreement", "evaluation", "pilot run",
            "process development", "msat", "upstream", "downstream", "cdmo selection",
        ],
    },
    "corporate": {
        "weight": 3,
        "keywords": [
            "acquisition", "merger", "divestiture", "funding", "financing",
            "regulatory milestone", "bla", "nda", "ema", "fda approval",
            "chief manufacturing officer", "svp manufacturing",
        ],
    },
}

# Optional per-company sources file (company press + RSS). If missing, fallback to Google News RSS only.
NEWS_SOURCES_PATH = Path(__file__).resolve().parent / "news_sources.json"


@st.cache_data
def _load_news_sources() -> dict:
    try:
        if NEWS_SOURCES_PATH.exists():
            return json.loads(NEWS_SOURCES_PATH.read_text(encoding="utf-8"))
    except Exception:
        pass
    return {}


def parse_rss_date(entry) -> datetime.date | None:
    try:
        if hasattr(entry, "published_parsed") and entry.published_parsed:
            dt = datetime.datetime(*entry.published_parsed[:6])
            return dt.date()
        if hasattr(entry, "updated_parsed") and entry.updated_parsed:
            dt = datetime.datetime(*entry.updated_parsed[:6])
            return dt.date()
    except Exception:
        pass
    return None


def compute_trigger_freshness_score(published_at: datetime.date | None) -> int:
    if published_at is None:
        return 0
    try:
        days = (datetime.date.today() - published_at).days
    except Exception:
        return 0
    if days <= 30:
        return 3
    if days <= 90:
        return 1
    return 0


def infer_trigger_type(text: str) -> str | None:
    if not text:
        return None
    t = text.lower()

    if any(k in t for k in ("funding", "raised", "series", "seed", "venture")):
        return "funding"
    if any(k in t for k in ("facility", "factory", "manufactur", "plant", "expansion")):
        return "facility_expansion"
    if any(k in t for k in ("acquir", "acquisition", "acquired", "bought")):
        return "acquisition"
    if any(k in t for k in ("divest", "spinoff", "spin-off", "sold")):
        return "divestiture"
    if any(k in t for k in ("partner", "partnership", "collaborat", "alliance", "joint venture")):
        return "partnership"
    if any(k in t for k in ("contract", "award", "won", "selected", "deal")):
        return "vendor_contract"
    if any(k in t for k in ("launch", "introduc", "released", "announce")):
        return "product_launch"
    if any(k in t for k in ("fda", "ce mark", "approval", "clearance", "regulator", "regulatory")):
        return "regulatory_milestone"
    if any(k in t for k in ("hire", "appointed", "joined", "named", "ceo", "cto")):
        return "new_hire"

    return "general_press"


def is_recent(published_at: datetime.date | None) -> bool:
    if published_at is None:
        return False
    try:
        return (datetime.date.today() - published_at).days <= MAX_TRIGGER_AGE_DAYS
    except Exception:
        return False


def _keyword_signal_score(text: str) -> int:
    if not text:
        return 0
    t = text.lower()
    score = 0
    for bucket in KEYWORD_SIGNALS.values():
        w = int(bucket.get("weight", 0))
        for k in bucket.get("keywords", []):
            if k and k in t:
                score += w
                break  # avoid double-counting within same bucket
    return score


def _find_company_sources(company_name: str) -> dict:
    """Return mapping with possible keys: 'rss' (str|None), 'press' (str|None)."""
    srcs = _load_news_sources()
    if not srcs:
        return {}
    if not company_name:
        return {}
    cn = str(company_name).strip().lower()
    # Try exact, then case-insensitive, then substring both ways
    for k, v in srcs.items():
        if k.strip().lower() == cn:
            return v or {}
    for k, v in srcs.items():
        if cn == k.strip().lower():
            return v or {}
    for k, v in srcs.items():
        kl = k.strip().lower()
        if cn in kl or kl in cn:
            return v or {}
    return {}


@st.cache_data(ttl=86400)
def fetch_company_news_from_rss(company_name: str, max_results: int = 10) -> list[dict]:
    if not company_name or str(company_name).strip() == "":
        return []
    # Prefer configured RSS for the specific company, else fallback to Google News RSS search
    preferred = _find_company_sources(company_name)
    rss_url = None
    try:
        rss_url = preferred.get("rss") if isinstance(preferred, dict) else None
    except Exception:
        rss_url = None
    if not rss_url:
        q = quote(str(company_name))
        rss_url = f"https://news.google.com/rss/search?q={q}"

    try:
        feed = feedparser.parse(rss_url)
    except Exception:
        return []

    items = []
    entries = getattr(feed, "entries", [])
    for e in entries[: max_results * 3]:
        try:
            title = getattr(e, "title", "")
            link = getattr(e, "link", "")
            pub = parse_rss_date(e)
            if not link:
                continue
            if not is_recent(pub):
                continue
            items.append({"title": title, "url": link, "published_at": pub})
            if len(items) >= max_results:
                break
        except Exception:
            continue
    return items


@st.cache_data(ttl=86400)
def find_best_trigger_for_company(company_name: str) -> dict | None:
    articles = fetch_company_news_from_rss(company_name, max_results=15)
    candidates = []
    for a in articles:
        title = a.get("title", "")
        url = a.get("url", "")
        pub = a.get("published_at")
        trigger_type = infer_trigger_type(title)
        type_score = TRIGGER_WEIGHTS.get(trigger_type, 0)
        freshness_score = compute_trigger_freshness_score(pub)
        signal_score = _keyword_signal_score(title)
        final_score = type_score + freshness_score + signal_score
        if final_score > 0:
            candidates.append({
                "title": title,
                "url": url,
                "published_at": pub,
                "trigger_type": trigger_type,
                "final_score": final_score,
            })

    if not candidates:
        return None

    candidates = sorted(candidates, key=lambda x: (-x["final_score"], x.get("published_at") or datetime.date.min))
    best = candidates[0]
    return {
        "external_trigger_title": best.get("title", ""),
        "external_trigger_url": best.get("url", ""),
        "external_trigger_type": best.get("trigger_type", ""),
        "external_trigger_score": int(best.get("final_score", 0)),
        "external_trigger_date": best.get("published_at"),
    }
