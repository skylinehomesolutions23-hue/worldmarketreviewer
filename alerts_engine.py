import os
from datetime import datetime
from typing import Any, Dict, List, Optional

import httpx


def _base_url() -> str:
    # Render primary URL should work, or local fallback.
    return (os.getenv("API_BASE") or "https://worldmarketreviewer.onrender.com").rstrip("/")


def _cron_key() -> str:
    return (os.getenv("ALERTS_CRON_KEY") or "").strip()


def _min_rank(label: str) -> int:
    lab = (label or "").upper().strip()
    if lab == "HIGH":
        return 3
    if lab == "MEDIUM":
        return 2
    if lab == "LOW":
        return 1
    return 0


def should_alert(pred: Dict[str, Any], min_confidence: str) -> bool:
    """
    pred: one item from /api/summary predictions list.
    """
    want = _min_rank(min_confidence)
    got = _min_rank(pred.get("confidence") or "")
    return got >= want


def fetch_predictions(tickers: List[str], horizon_days: int = 5, source_pref: str = "auto") -> Dict[str, Any]:
    """
    Calls your own backend /api/summary to get predictions.
    """
    url = f"{_base_url()}/api/summary"
    payload = {
        "tickers": tickers,
        "horizon_days": int(horizon_days),
        "retrain": True,
        "max_parallel": 1,
        "source_pref": source_pref,
    }

    with httpx.Client(timeout=30.0, follow_redirects=True) as client:
        r = client.post(url, json=payload)
        r.raise_for_status()
        return r.json()


def build_alert_items(summary_json: Dict[str, Any], min_confidence: str) -> List[Dict[str, Any]]:
    preds = summary_json.get("predictions") or []
    items = []
    for p in preds:
        if should_alert(p, min_confidence=min_confidence):
            items.append(p)
    return items


def smtp_configured() -> bool:
    # Placeholder: you’ll wire actual SMTP later.
    # For now this returns False so health endpoint can show status.
    return bool(os.getenv("SMTP_HOST")) and bool(os.getenv("SMTP_USER"))
