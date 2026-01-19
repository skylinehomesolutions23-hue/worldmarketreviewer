# news_provider.py
import re
import time
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional
from urllib.parse import urlencode
from urllib.request import Request, urlopen


def _http_get_json(url: str, timeout: int = 15) -> Dict[str, Any]:
    """
    No external deps (no requests). Uses urllib.
    """
    headers = {
        "User-Agent": "WorldMarketReviewer/1.0 (+https://worldmarketreviewer.onrender.com)",
        "Accept": "application/json",
    }
    req = Request(url, headers=headers)
    with urlopen(req, timeout=timeout) as resp:
        raw = resp.read().decode("utf-8", errors="replace")
    import json
    return json.loads(raw)


def _safe_int(x: Any, default: int) -> int:
    try:
        return int(x)
    except Exception:
        return default


def _iso_utc(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def _clean_text(s: Any) -> str:
    txt = "" if s is None else str(s)
    txt = re.sub(r"\s+", " ", txt).strip()
    return txt


def fetch_news_gdelt(
    ticker: str,
    limit: int = 20,
    hours_back: int = 72,
    mode: str = "list",
) -> Dict[str, Any]:
    """
    GDELT 2.1 DOC API:
    - free, no key
    - good for headlines / URLs
    """
    t = _clean_text(ticker).upper()
    limit = max(1, min(50, _safe_int(limit, 20)))
    hours_back = max(6, min(24 * 30, _safe_int(hours_back, 72)))

    now = datetime.utcnow()
    start = now - timedelta(hours=hours_back)

    # Query strategy:
    # - Use the ticker as the query term (works well for SPY/QQQ/NVDA etc.)
    # - You can later improve this by mapping tickers -> company name(s)
    query = t

    params = {
        "query": query,
        "mode": mode,              # "list" is simplest
        "format": "json",
        "maxrecords": str(limit),
        "startdatetime": start.strftime("%Y%m%d%H%M%S"),
        "enddatetime": now.strftime("%Y%m%d%H%M%S"),
        "sort": "HybridRel",
        "format": "json",
    }

    url = "https://api.gdeltproject.org/api/v2/doc/doc?" + urlencode(params)

    t0 = time.time()
    data = _http_get_json(url, timeout=15)
    ms = int((time.time() - t0) * 1000)

    articles: List[Dict[str, Any]] = []
    for a in data.get("articles", []) or []:
        articles.append({
            "title": _clean_text(a.get("title")),
            "url": _clean_text(a.get("url")),
            "sourceCountry": _clean_text(a.get("sourceCountry")),
            "sourceCollection": _clean_text(a.get("sourceCollection")),
            "domain": _clean_text(a.get("domain")),
            "language": _clean_text(a.get("language")),
            "seendate": _clean_text(a.get("seendate")),
        })

    return {
        "ok": True,
        "provider": "gdelt",
        "ticker": t,
        "query": query,
        "limit": limit,
        "hours_back": hours_back,
        "fetched": len(articles),
        "latency_ms": ms,
        "articles": articles,
        "note": "Free headlines via GDELT. This is not sentiment, just news discovery.",
        "time_utc": _iso_utc(datetime.utcnow()),
    }


def fetch_news(
    ticker: str,
    limit: int = 20,
    hours_back: int = 72,
    provider: str = "gdelt",
) -> Dict[str, Any]:
    p = (provider or "gdelt").lower().strip()
    if p == "gdelt":
        return fetch_news_gdelt(ticker=ticker, limit=limit, hours_back=hours_back)
    return {
        "ok": False,
        "provider": p,
        "ticker": (ticker or "").upper().strip(),
        "error": f"Unknown provider: {provider}",
        "time_utc": _iso_utc(datetime.utcnow()),
    }
