# api_news_router.py
from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Query

from news_gdelt import fetch_gdelt_news

router = APIRouter()


@router.get("/api/news")
async def api_news(
    ticker: str = Query(..., description="Single ticker like TSLA"),
    days: int = Query(7, ge=1, le=30, description="How many days back (1-30)"),
    limit: int = Query(20, ge=1, le=50, description="How many headlines (1-50)"),
) -> Dict[str, Any]:
    items = await fetch_gdelt_news(ticker, days=days, limit=limit)
    return {
        "ticker": ticker.strip().upper(),
        "days": days,
        "limit": limit,
        "items": [
            {
                "title": x.title,
                "url": x.url,
                "domain": x.domain,
                "seenDate": x.seenDate,
                "socialImage": x.socialImage,
                "sourceCountry": x.sourceCountry,
                "language": x.language,
            }
            for x in items
        ],
    }
