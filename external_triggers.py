import os
import time
from typing import List, Optional
import urllib.parse

import requests
import streamlit as st

try:
    import feedparser
except Exception:
    feedparser = None

TRIGGER_WEIGHTS = {
    "funding": 3,
    "facility_expansion": 3,
    "new_hire": 2,
    "partnership": 2,
    "general_press": 1,
}


def infer_trigger_type(text: str) -> Optional[str]:
    if not text or not isinstance(text, str) or not text.strip():
        return None
    t = text.lower()
    if any(k in t for k in ("raises", "series a", "series b", "series c", "$", "raised")):
        return "funding"
    if any(k in t for k in ("expands", "new facility", "new plant", "manufacturing site", "expansion", "inaugur")):
        return "facility_expansion"
    if any(k in t for k in ("appoints", "hires", "joins as", "new vp", "new director", "named as")):
        return "new_hire"
    if any(k in t for k in ("partners with", "collaborates with", "in collaboration with", "partnered with")):
        return "partnership"
    return "general_press"


def _fetch_google_news_rss(company_name: str, max_results: int = 5) -> List[dict]:
    q = urllib.parse.quote(company_name)
    url = f"https://news.google.com/rss/search?q={q}"
    try:
        if feedparser:
            feed = feedparser.parse(url)
            items = []
            for e in (feed.entries or [])[:max_results]:
                items.append({
                    "title": e.get("title", ""),
                    "url": e.get("link", ""),
                    "published_at": e.get("published", ""),
                    "source": e.get("source", {}).get("title", "") if isinstance(e.get("source"), dict) else "",
                })
            return items
        else:
            r = requests.get(url, timeout=10)
            if r.status_code != 200:
                return []
            # naive XML parse
            from xml.etree import ElementTree as ET

            root = ET.fromstring(r.content)
            items = []
            for item in root.findall('.//item')[:max_results]:
                title = item.findtext('title') or ""
                link = item.findtext('link') or ""
                pub = item.findtext('pubDate') or ""
                items.append({"title": title, "url": link, "published_at": pub, "source": "Google News"})
            return items
    except Exception:
        return []


def _fetch_newsapi(company_name: str, api_key: str, max_results: int = 5) -> List[dict]:
    url = "https://newsapi.org/v2/everything"
    q = f'"{company_name}" bioprocess OR biologics OR manufacturing'
    params = {"q": q, "pageSize": max_results, "language": "en", "sortBy": "publishedAt", "apiKey": api_key}
    try:
        r = requests.get(url, params=params, timeout=10)
        if r.status_code != 200:
            return []
        j = r.json()
        items = []
        for a in j.get("articles", [])[:max_results]:
            items.append({
                "title": a.get("title", ""),
                "url": a.get("url", ""),
                "published_at": a.get("publishedAt", ""),
                "source": a.get("source", {}).get("name", ""),
            })
        return items
    except Exception:
        return []


@st.cache_data(show_spinner=False)
def fetch_company_news(company_name: str, max_results: int = 5) -> List[dict]:
    company_name = (company_name or "").strip()
    if not company_name:
        return []

    results = []

    newsapi_key = None
    try:
        newsapi_key = st.secrets.get("NEWSAPI_KEY") if hasattr(st, "secrets") else None
    except Exception:
        newsapi_key = os.environ.get("NEWSAPI_KEY")

    if newsapi_key:
        results.extend(_fetch_newsapi(company_name, newsapi_key, max_results=max_results))

    # always try Google News RSS as fallback/augment
    results.extend(_fetch_google_news_rss(company_name, max_results=max_results))

    # dedupe by url
    seen = set()
    out = []
    for r in results:
        url = r.get("url") or r.get("link") or ""
        if not url:
            continue
        if url in seen:
            continue
        seen.add(url)
        out.append(r)
    return out


@st.cache_data(show_spinner=False)
def find_best_trigger_for_company(company_name: str) -> Optional[dict]:
    articles = fetch_company_news(company_name, max_results=8)
    if not articles:
        return None

    best = None
    best_score = -1
    best_time = None

    for a in articles:
        title = a.get("title", "") or ""
        snippet = a.get("description", "") or ""
        txt = (title + " " + snippet).strip()
        ttype = infer_trigger_type(txt)
        score = TRIGGER_WEIGHTS.get(ttype, 0)
        # parse published time for tie-breaking if available
        pub = a.get("published_at")
        # simple epoch fallback
        try:
            # try ISO parse
            from dateutil import parser as _p

            pub_dt = _p.parse(pub) if pub else None
        except Exception:
            pub_dt = None

        if score > best_score or (score == best_score and pub_dt and (best_time is None or pub_dt > best_time)):
            best = {
                "external_trigger_title": title,
                "external_trigger_url": a.get("url", ""),
                "external_trigger_type": ttype,
                "external_trigger_score": int(score),
            }
            best_score = score
            best_time = pub_dt

    return best
