# news_gdelt.py
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional
from urllib.parse import quote_plus

import httpx


@dataclass
class NewsItem:
    title: str
    url: str
    domain: Optional[str]
    seenDate: Optional[str]
    socialImage: Optional[str]
    sourceCountry: Optional[str]
    language: Optional[str]


def _safe_get(d: Dict[str, Any], key: str) -> Optional[str]:
    v = d.get(key)
    if v is None:
        return None
    if isinstance(v, str):
        return v
    return str(v)


async def fetch_gdelt_news(
    ticker: str,
    *,
    days: int = 7,
    limit: int = 20,
    timeout_s: float = 12.0,
) -> List[NewsItem]:
    """
    Uses GDELT DOC 2.0 API Article List (mode=artlist) and JSON output.
    - timespan supports values like "7d", "1week", "24h", etc.
    - maxrecords can be up to 250, default is lower. :contentReference[oaicite:1]{index=1}
    """
    t = ticker.strip().upper()
    if not t:
        return []

    # Simple query: ticker OR quoted ticker.
    # You can improve later (company name mapping), but this ships now.
    query = f'({t} OR "{t}")'

    # Clamp parameters safely
    days = max(1, min(int(days), 30))          # keep it sane
    limit = max(1, min(int(limit), 50))        # fast + friendly
    timespan = f"{days}d"

    base = "https://api.gdeltproject.org/api/v2/doc/doc"
    url = (
        f"{base}"
        f"?query={quote_plus(query)}"
        f"&mode=artlist"
        f"&format=json"
        f"&sort=datedesc"
        f"&maxrecords={limit}"
        f"&timespan={quote_plus(timespan)}"
    )

    async with httpx.AsyncClient(timeout=timeout_s) as client:
        r = await client.get(url)
        r.raise_for_status()
        data = r.json()

    articles = data.get("articles", []) or []

    out: List[NewsItem] = []
    for a in articles:
        out.append(
            NewsItem(
                title=_safe_get(a, "title") or "(untitled)",
                url=_safe_get(a, "url") or "",
                domain=_safe_get(a, "domain"),
                seenDate=_safe_get(a, "seendate"),
                socialImage=_safe_get(a, "socialimage"),
                sourceCountry=_safe_get(a, "sourcecountry"),
                language=_safe_get(a, "language"),
            )
        )

    # Filter bad rows
    out = [x for x in out if x.url]
    return out
