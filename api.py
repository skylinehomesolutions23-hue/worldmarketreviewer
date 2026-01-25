import math
from datetime import datetime
from typing import List, Optional, Dict, Any, Tuple
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from urllib.parse import quote_plus

import httpx
import os
from fastapi import FastAPI
from fastapi.responses import Response, HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from main_autobatch import TICKERS
from data_loader import load_stock_data
from feature_engineering import build_features
from walk_forward import walk_forward_predict_proba

from alerts_db import init_alerts_db
from alerts_router import router as alerts_router

from db import (
    init_db,
    insert_predictions,
    get_latest_run_id,
    get_predictions_for_run,
    create_run,
    update_run_progress,
    finish_run,
    get_run_state,
    # scoring additions
    get_unscored_predictions,
    set_prediction_score,
    get_scoreboard,
)

BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"

app = FastAPI(title="WorldMarketReviewer API")
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
app.include_router(alerts_router)


# -----------------------------
# helpers
# -----------------------------
def json_safe(x):
    if x is None:
        return None
    try:
        if isinstance(x, float) and (math.isnan(x) or math.isinf(x)):
            return None
        return x
    except Exception:
        return None


def clamp01(x: Any) -> Optional[float]:
    try:
        n = float(x)
        if not math.isfinite(n):
            return None
        return max(0.0, min(1.0, n))
    except Exception:
        return None


def compute_expected_return_from_prob(prob_up: float, base_move: float = 0.02) -> float:
    prob_up = max(0.0, min(1.0, float(prob_up)))
    return (2.0 * prob_up - 1.0) * float(base_move)


def confidence_score(prob_up: Optional[float]) -> Optional[float]:
    """
    0.0 means coin flip (0.50). 1.0 means extreme (0 or 1).
    """
    if prob_up is None:
        return None
    p = clamp01(prob_up)
    if p is None:
        return None
    return abs(p - 0.5) * 2.0


def confidence_label(prob_up: Optional[float]) -> str:
    """
    Based on distance from 0.5 (|p-0.5|):
      LOW    : 0.50–0.55
      MEDIUM : 0.55–0.65
      HIGH   : 0.65+
    """
    cs = confidence_score(prob_up)
    if cs is None:
        return "UNKNOWN"
    if cs >= 0.30:
        return "HIGH"
    if cs >= 0.10:
        return "MEDIUM"
    return "LOW"


def _to_date_key(s: str) -> str:
    s = (s or "").strip()
    if not s:
        return ""
    if len(s) >= 10 and s[4] == "-" and s[7] == "-":
        return s[:10]
    return s


def _load_prices(
    ticker: str,
    freq: str = "daily",
    lookback_days: int = 365 * 6,
    source_pref: str = "auto",
) -> Any:
    t = (ticker or "").upper().strip()
    source_pref = (source_pref or "auto").lower().strip()
    try:
        return load_stock_data(t, freq=freq, lookback_days=int(lookback_days), source=source_pref)
    except TypeError:
        # older load_stock_data signature fallback
        return load_stock_data(t, freq=freq, lookback_days=int(lookback_days))


def _find_close_col(df) -> Optional[str]:
    if df is None or getattr(df, "empty", True):
        return None

    for c in ["close", "Close", "adj_close", "Adj Close", "adjclose", "AdjClose", "Price"]:
        if c in df.columns:
            return c

    for c in df.columns:
        try:
            sample = df[c].dropna().iloc[:3].tolist()
            if sample and all(isinstance(v, (int, float)) for v in sample):
                return c
        except Exception:
            continue

    return None


def _sparkline_from_df(df, n: int) -> Dict[str, Any]:
    if df is None or df.empty:
        return {"closes": [], "dates": [], "rows": 0, "source": "unknown"}

    close_col = _find_close_col(df)
    if close_col is None:
        return {
            "closes": [],
            "dates": [],
            "rows": int(len(df)),
            "source": df.attrs.get("source", "unknown"),
            "note": "No close-like column found.",
        }

    tail = df.tail(max(2, int(n))).copy()

    closes: List[float] = []
    dates: List[str] = []

    try:
        idx = list(tail.index)
    except Exception:
        idx = [None] * len(tail)

    series = tail[close_col]

    for i, v in enumerate(series.tolist()):
        try:
            fv = float(v)
            if not math.isfinite(fv):
                continue
        except Exception:
            continue

        closes.append(fv)
        d = None
        try:
            if idx[i] is not None:
                d = str(idx[i])
        except Exception:
            d = None
        dates.append(d or "")

    return {
        "closes": closes,
        "dates": dates,
        "rows": int(len(df)),
        "source": df.attrs.get("source", "unknown"),
        "close_col": close_col,
    }


def _pct_change(a: Optional[float], b: Optional[float]) -> Optional[float]:
    try:
        if a is None or b is None:
            return None
        a = float(a)
        b = float(b)
        if not math.isfinite(a) or not math.isfinite(b) or a == 0.0:
            return None
        return b / a - 1.0
    except Exception:
        return None


def _extract_as_of(df) -> Tuple[Optional[str], Optional[float], Optional[str]]:
    payload = _sparkline_from_df(df, n=3)
    closes = payload.get("closes") or []
    dates = payload.get("dates") or []
    if not closes or not dates:
        return None, None, payload.get("close_col")
    return dates[-1], closes[-1], payload.get("close_col")


# -----------------------------
# news (GDELT)
# -----------------------------
def _hours_to_timespan(hours_back: int) -> str:
    """
    GDELT timespan supports minutes/hours/days/weeks/months like:
      72h, 7d, 1w, 1m, etc. :contentReference[oaicite:1]{index=1}
    """
    hb = max(1, int(hours_back))
    # Prefer days if it divides cleanly and is >= 24h
    if hb >= 24 and hb % 24 == 0:
        d = hb // 24
        return f"{d}d"
    return f"{hb}h"

def _news_query_for_ticker(t: str) -> str:
    """
    GDELT rejects very short phrases like 'TSLA'.
    Use a slightly longer, human-readable query.
    """
    t = (t or "").upper().strip()

    # Add mappings as you expand your ticker list
    alias = {
        "TSLA": '"Tesla"',
        "META": '"Meta" OR "Facebook"',
        "GOOGL": '"Google" OR "Alphabet"',
        "GOOG": '"Google" OR "Alphabet"',
        "AAPL": '"Apple"',
        "AMZN": '"Amazon"',
        "MSFT": '"Microsoft"',
        "NVDA": '"Nvidia"',
        "NFLX": '"Netflix"',
        "AMD": '"AMD" OR "Advanced Micro Devices"',
        "INTC": '"Intel"',
        "JPM": '"JPMorgan" OR "JP Morgan"',
        "BAC": '"Bank of America"',
        "GS": '"Goldman Sachs"',
        "MS": '"Morgan Stanley"',
        "XOM": '"Exxon" OR "ExxonMobil"',
        "CVX": '"Chevron"',
        "SPY": '"S&P 500" OR SPY',
        "QQQ": '"Nasdaq 100" OR QQQ',
        "IWM": '"Russell 2000" OR IWM',
    }

    if t in alias:
        return alias[t]

    # Fallback: quote the ticker + add "stock" to make phrase longer
    # Example: "TSLA stock" / "SPY stock"
    return f'"{t} stock"'


def fetch_news(
    ticker: str,
    limit: int = 20,
    hours_back: int = 72,
    provider: str = "gdelt",
) -> Dict[str, Any]:
    provider = (provider or "gdelt").lower().strip()
    t = (ticker or "").upper().strip()
    limit = max(1, min(50, int(limit)))
    hours_back = max(6, min(24 * 30, int(hours_back)))

    if provider != "gdelt":
        return {"ok": False, "provider": provider, "ticker": t, "error": "Only provider=gdelt is supported right now."}

    if not t:
        return {"ok": False, "provider": provider, "ticker": t, "error": "Missing ticker."}

    query = _news_query_for_ticker(t)
    timespan = _hours_to_timespan(hours_back)

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

    headers = {
        # Some public endpoints behave better with an explicit UA.
        "User-Agent": "WorldMarketReviewer/0.9 (+https://example.invalid)",
        "Accept": "application/json,text/plain,*/*",
    }

    try:
        with httpx.Client(timeout=20.0, follow_redirects=True, headers=headers) as client:
            r = client.get(url)
            status = r.status_code
            ctype = (r.headers.get("content-type") or "").lower()
            text = (r.text or "").strip()

            # Helpful debug info when it fails
            if status != 200:
                return {
                    "ok": False,
                    "provider": provider,
                    "ticker": t,
                    "error": f"HTTP {status}",
                    "content_type": ctype,
                    "url": url,
                    "body_preview": text[:300],
                    "note": "News provider returned non-200.",
                    "time_utc": datetime.utcnow().isoformat(timespec="seconds") + "Z",
                }

            if not text:
                return {
                    "ok": False,
                    "provider": provider,
                    "ticker": t,
                    "error": "Empty response body from provider",
                    "content_type": ctype,
                    "url": url,
                    "note": "News provider returned empty body.",
                    "time_utc": datetime.utcnow().isoformat(timespec="seconds") + "Z",
                }

            # If we got HTML, we know it's not JSON.
            if "text/html" in ctype or text.startswith("<!doctype") or text.startswith("<html"):
                return {
                    "ok": False,
                    "provider": provider,
                    "ticker": t,
                    "error": "Provider returned HTML instead of JSON",
                    "content_type": ctype,
                    "url": url,
                    "body_preview": text[:300],
                    "note": "Likely an upstream error page / block / redirect.",
                    "time_utc": datetime.utcnow().isoformat(timespec="seconds") + "Z",
                }

            # Parse JSON safely
            try:
                data = r.json()
            except Exception as e:
                return {
                    "ok": False,
                    "provider": provider,
                    "ticker": t,
                    "error": f"JSON parse failed: {e}",
                    "content_type": ctype,
                    "url": url,
                    "body_preview": text[:300],
                    "note": "Provider returned non-JSON or malformed JSON.",
                    "time_utc": datetime.utcnow().isoformat(timespec="seconds") + "Z",
                }

    except Exception as e:
        return {
            "ok": False,
            "provider": provider,
            "ticker": t,
            "error": str(e),
            "url": url,
            "note": "Request failed (timeout/network).",
            "time_utc": datetime.utcnow().isoformat(timespec="seconds") + "Z",
        }

    articles = data.get("articles", []) or []
    items: List[Dict[str, Any]] = []
    for a in articles:
        url_a = a.get("url")
        if not url_a:
            continue
        items.append(
            {
                "title": a.get("title") or "(untitled)",
                "url": url_a,
                "domain": a.get("domain"),
                "seendate": a.get("seendate"),
                "socialimage": a.get("socialimage"),
                "sourcecountry": a.get("sourcecountry"),
                "language": a.get("language"),
            }
        )

    return {
        "ok": True,
        "provider": provider,
        "ticker": t,
        "limit": limit,
        "hours_back": hours_back,
        "timespan": timespan,
        "items": items,
        "time_utc": datetime.utcnow().isoformat(timespec="seconds") + "Z",
    }



# -----------------------------
# core prediction
# -----------------------------
def _run_one_ticker(
    ticker: str,
    horizon_days: int,
    base_weekly_move: float,
    retrain: bool = True,
    source_pref: str = "auto",
) -> Dict[str, Any]:
    t = ticker.upper().strip()

    df = _load_prices(t, freq="daily", lookback_days=365 * 6, source_pref=source_pref)
    if df is None or len(df) < 30:
        raise ValueError("Not enough data")

    source = df.attrs.get("source", "unknown")

    as_of_date, as_of_close, _ = _extract_as_of(df)

    df_feat = build_features(df, horizon_days=horizon_days)
    feature_cols = [c for c in df_feat.columns if c not in ["target", "date"]]

    probs = walk_forward_predict_proba(
        df_feat,
        feature_cols=feature_cols,
        target_col="target",
        ticker=t,
        horizon_days=horizon_days,
        retrain=retrain,
        lookback=252,
        min_train=60,
    )
    prob_up = float(probs.iloc[-1])

    exp_return = compute_expected_return_from_prob(prob_up, base_move=base_weekly_move)
    direction = "UP" if prob_up >= 0.5 else "DOWN"

    return {
        "ticker": t,
        "source": source,
        "prob_up": json_safe(prob_up),
        "exp_return": json_safe(exp_return),
        "direction": direction,
        "horizon_days": int(horizon_days),
        "as_of_date": as_of_date,
        "as_of_close": json_safe(as_of_close),
        "confidence_score": json_safe(confidence_score(prob_up)),
        "confidence": confidence_label(prob_up),
    }


def _score_one_prediction_row(row: Dict[str, Any], source_pref: str = "auto") -> Tuple[int, str, str, Optional[float], Optional[str], str]:
    pred_id = int(row["id"])
    ticker = (row.get("ticker") or "").upper().strip()
    as_of_date = row.get("as_of_date") or ""
    as_of_key = _to_date_key(str(as_of_date))
    horizon_days = int(row.get("horizon_days") or 5)

    if not ticker or not as_of_key:
        return pred_id, ticker, as_of_key, None, None, "missing_asof"

    df = _load_prices(ticker, freq="daily", lookback_days=365 * 6, source_pref=source_pref)
    if df is None or getattr(df, "empty", True):
        return pred_id, ticker, as_of_key, None, None, "no_data"

    close_col = _find_close_col(df)
    if close_col is None:
        return pred_id, ticker, as_of_key, None, None, "no_close_col"

    try:
        idx_strs = [str(x) for x in df.index]
    except Exception:
        return pred_id, ticker, as_of_key, None, None, "no_data"

    idx_keys = [_to_date_key(s) for s in idx_strs]

    try:
        pos = idx_keys.index(as_of_key)
    except ValueError:
        return pred_id, ticker, as_of_key, None, None, "asof_not_found"

    target_pos = pos + horizon_days
    if target_pos >= len(df):
        return pred_id, ticker, as_of_key, None, None, "not_matured"

    try:
        as_of_close = float(df.iloc[pos][close_col])
        target_close = float(df.iloc[target_pos][close_col])
        if not math.isfinite(as_of_close) or not math.isfinite(target_close) or as_of_close == 0.0:
            return pred_id, ticker, as_of_key, None, None, "no_data"
    except Exception:
        return pred_id, ticker, as_of_key, None, None, "no_data"

    realized_return = target_close / as_of_close - 1.0
    realized_direction = "UP" if realized_return >= 0 else "DOWN"
    return pred_id, ticker, as_of_key, realized_return, realized_direction, "scored"


# -----------------------------
# request models
# -----------------------------
class PredictRequest(BaseModel):
    tickers: Optional[List[str]] = None
    all: bool = False
    horizon_days: int = 5
    base_weekly_move: float = 0.02
    max_parallel: int = 1
    retrain: bool = True
    source_pref: Optional[str] = "auto"  # NEW


class SummaryRequest(BaseModel):
    tickers: Optional[List[str]] = None
    retrain: bool = True
    horizon_days: int = 5
    base_weekly_move: float = 0.02
    max_parallel: int = 1
    min_confidence: Optional[str] = None  # LOW / MEDIUM / HIGH
    min_prob_up: Optional[float] = None   # optional numeric filter (UP only)
    source_pref: Optional[str] = "auto"   # NEW


# -----------------------------
# startup
# -----------------------------
@app.on_event("startup")
def _startup():
    if not os.getenv("DATABASE_URL"):
        print("[startup] DATABASE_URL not set; skipping init_db/init_alerts_db (local dev).")
        return

    # ---- main DB (predictions, run_state) ----
    try:
        r = init_db()
        if isinstance(r, dict) and not r.get("ok", True):
            print("[startup][WARN] init_db failed, app will continue:", r.get("error"))
    except Exception as e:
        print("[startup][WARN] init_db exception, app will continue:", str(e))

    # ---- alerts DB ----
    try:
        r2 = init_alerts_db()
        if isinstance(r2, dict) and not r2.get("ok", True):
            print("[startup][WARN] init_alerts_db failed, app will continue:", r2.get("error"))
    except Exception as e:
        print("[startup][WARN] init_alerts_db exception, app will continue:", str(e))



@app.get("/health")
def health():
    return {
        "status": "ok",
        "service": "worldmarketreviewer",
        "version": "0.9.1",
        "time_utc": datetime.utcnow().isoformat(timespec="seconds") + "Z",
    }


# -----------------------------
# education & configuration
# -----------------------------
@app.get("/api/data_sources")
def data_sources():
    return {
        "default": "auto",
        "supported_preferences": ["auto", "cache", "live"],
        "note": "Endpoints that accept source_pref will route data loading accordingly.",
    }


@app.get("/api/news")
def news(
    ticker: str = "SPY",
    limit: int = 20,
    hours_back: int = 72,
    provider: str = "gdelt",
):
    t = (ticker or "").upper().strip()
    limit = max(1, min(50, int(limit)))
    hours_back = max(6, min(24 * 30, int(hours_back)))
    provider = (provider or "gdelt").lower().strip()

    return fetch_news(ticker=t, limit=limit, hours_back=hours_back, provider=provider)


@app.get("/api/explain")
def explain():
    return {
        "what_this_app_does": (
            "For each ticker, the backend loads daily prices, builds technical features, "
            "and uses a walk-forward RandomForest model to estimate the probability the price "
            "will be higher after N trading days (horizon_days)."
        ),
        "fields": {
            "direction": "UP means prob_up >= 0.50, DOWN means prob_up < 0.50.",
            "prob_up": "Probability (0–1) the price will be up after the horizon. Not a guarantee.",
            "confidence": "LOW/MEDIUM/HIGH based on how far prob_up is from 0.50.",
            "confidence_score": "0.0 is coin flip; 1.0 is extreme confidence (near 0 or 1).",
            "exp_return": "A simple proxy derived from prob_up. Educational only.",
            "horizon_days": "How many trading days ahead the prediction targets (e.g., 5).",
            "as_of_date": "The last price date used when generating that prediction.",
            "scoring": "Later, we check what actually happened after horizon_days and compute accuracy.",
            "source_pref": "auto/cache/live controls whether to prefer cache or force fresh data.",
        },
        "important": [
            "Markets are uncertain. 100% accuracy is impossible.",
            "The goal is measurable edge + transparency, not certainty.",
        ],
    }


# -----------------------------
# static + misc
# -----------------------------
@app.get("/api/tickers")
def tickers():
    return {"count": len(TICKERS), "tickers": TICKERS}


@app.get("/app", response_class=HTMLResponse)
def mobile_app():
    app_file = STATIC_DIR / "app.html"
    if not app_file.exists():
        return HTMLResponse("static/app.html not found.", status_code=500)
    return app_file.read_text(encoding="utf-8")


@app.head("/api/summary")
def summary_head():
    return Response(status_code=200)


@app.get("/api/debug_prices")
def debug_prices(ticker: str = "SPY", freq: str = "daily", lookback_days: int = 365 * 6, source_pref: str = "auto"):
    t = (ticker or "").upper().strip()
    df = _load_prices(t, freq=freq, lookback_days=int(lookback_days), source_pref=source_pref)
    if df is None or df.empty:
        return {"ticker": t, "ok": False, "note": "load_stock_data returned None/empty."}

    return {
        "ticker": t,
        "ok": True,
        "freq": freq,
        "source_pref": source_pref,
        "source": df.attrs.get("source", "unknown"),
        "rows": int(len(df)),
        "start": str(df.index.min()),
        "end": str(df.index.max()),
        "cols": list(df.columns),
        "tail": df.tail(3).reset_index().to_dict(orient="records"),
    }


# -----------------------------
# sparklines
# -----------------------------
@app.get("/api/sparkline")
def sparkline(ticker: str = "SPY", n: int = 60, lookback_days: int = 120, source_pref: str = "auto"):
    t = (ticker or "").upper().strip()
    n = max(2, min(365, int(n)))
    lookback_days = max(n + 5, min(365 * 6, int(lookback_days)))

    df = _load_prices(t, freq="daily", lookback_days=lookback_days, source_pref=source_pref)
    if df is None or df.empty:
        return {"ticker": t, "n": n, "closes": [], "dates": [], "ok": False, "note": "No data returned."}

    payload = _sparkline_from_df(df, n=n)
    closes = (payload.get("closes") or [])[-n:]
    dates = (payload.get("dates") or [])[-n:]

    return {
        "ticker": t,
        "n": n,
        "closes": closes,
        "dates": dates,
        "source_pref": source_pref,
        "source": payload.get("source", df.attrs.get("source", "unknown")),
        "rows": payload.get("rows", int(len(df))),
        "close_col": payload.get("close_col"),
        "ok": True,
    }


@app.get("/api/sparklines")
def sparklines(
    tickers: str = "SPY,QQQ",
    n: int = 60,
    lookback_days: int = 120,
    max_parallel: int = 6,
    source_pref: str = "auto",
):
    raw = (tickers or "").strip()
    parts = [p.strip().upper() for p in raw.replace(" ", ",").split(",") if p.strip()]
    seen = set()
    tickers_list: List[str] = []
    for t in parts:
        if t and t not in seen:
            seen.add(t)
            tickers_list.append(t)
    if not tickers_list:
        tickers_list = ["SPY", "QQQ"]

    n = max(2, min(365, int(n)))
    lookback_days = max(n + 5, min(365 * 6, int(lookback_days)))
    max_parallel = max(1, min(16, int(max_parallel)))

    data: Dict[str, Any] = {}
    errors: Dict[str, str] = {}

    def one(t: str):
        df = _load_prices(t, freq="daily", lookback_days=lookback_days, source_pref=source_pref)
        if df is None or df.empty:
            return t, None, "No data."
        payload = _sparkline_from_df(df, n=n)
        closes = (payload.get("closes") or [])[-n:]
        dates = (payload.get("dates") or [])[-n:]
        if len(closes) < 2:
            return t, None, "Not enough close values."
        out = {
            "ticker": t,
            "n": n,
            "closes": closes,
            "dates": dates,
            "source_pref": source_pref,
            "source": payload.get("source", df.attrs.get("source", "unknown")),
            "rows": payload.get("rows", int(len(df))),
            "close_col": payload.get("close_col"),
            "ok": True,
        }
        return t, out, None

    if max_parallel == 1 or len(tickers_list) == 1:
        for t in tickers_list:
            try:
                tk, out, err = one(t)
                if err:
                    errors[tk] = err
                else:
                    data[tk] = out
            except Exception as e:
                errors[t] = str(e)
    else:
        with ThreadPoolExecutor(max_workers=max_parallel) as ex:
            futs = {ex.submit(one, t): t for t in tickers_list}
            for fut in as_completed(futs):
                t = futs[fut]
                try:
                    tk, out, err = fut.result()
                    if err:
                        errors[tk] = err
                    else:
                        data[tk] = out
                except Exception as e:
                    errors[t] = str(e)

    return {
        "n": n,
        "count": len(tickers_list),
        "returned": len(data),
        "data": data,
        "errors": errors,
        "tickers": tickers_list,
        "source_pref": source_pref,
    }


# -----------------------------
# manual verify
# -----------------------------
@app.get("/api/verify")
def verify(
    ticker: str = "SPY",
    horizon_days: int = 5,
    n: int = 60,
    lookback_days: int = 180,
    source_pref: str = "auto",
):
    t = (ticker or "").upper().strip()
    horizon_days = max(1, min(60, int(horizon_days)))
    n = max(10, min(365, int(n)))
    lookback_days = max(n + horizon_days + 5, min(365 * 6, int(lookback_days)))

    df = _load_prices(t, freq="daily", lookback_days=lookback_days, source_pref=source_pref)
    if df is None or df.empty:
        return {"ticker": t, "ok": False, "note": "No data returned.", "source_pref": source_pref}

    payload = _sparkline_from_df(df, n=max(n, horizon_days + 2))
    closes = payload.get("closes") or []
    dates = payload.get("dates") or []

    if len(closes) < horizon_days + 2:
        return {
            "ticker": t,
            "ok": False,
            "note": "Not enough closes to compute horizon return.",
            "rows": payload.get("rows", int(len(df))),
            "source_pref": source_pref,
        }

    last_close = closes[-1]
    prev_close = closes[-2]
    start_h_close = closes[-(horizon_days + 1)]

    ret_1d = _pct_change(prev_close, last_close)
    ret_h = _pct_change(start_h_close, last_close)

    dir_1d = "UP" if (ret_1d is not None and ret_1d >= 0) else "DOWN"
    dir_h = "UP" if (ret_h is not None and ret_h >= 0) else "DOWN"

    closes_n = closes[-n:]
    dates_n = dates[-n:]

    return {
        "ticker": t,
        "ok": True,
        "horizon_days": horizon_days,
        "source_pref": source_pref,
        "source": payload.get("source", df.attrs.get("source", "unknown")),
        "close_col": payload.get("close_col"),
        "last": {"close": last_close, "date": dates[-1] if dates else ""},
        "realized": {
            "return_1d": json_safe(ret_1d),
            "direction_1d": dir_1d,
            "return_horizon": json_safe(ret_h),
            "direction_horizon": dir_h,
            "horizon_start_close": start_h_close,
            "horizon_start_date": dates[-(horizon_days + 1)] if dates else "",
        },
        "series": {"n": len(closes_n), "closes": closes_n, "dates": dates_n},
        "note": (
            "This endpoint shows realized past returns into the most recent close. "
            "For true accuracy, use /api/score_predictions + /api/metrics which score stored predictions."
        ),
    }


# -----------------------------
# scoring + report cards
# -----------------------------
@app.post("/api/score_predictions")
def score_predictions(limit: int = 200, max_parallel: int = 4, source_pref: str = "auto"):
    limit = max(1, min(2000, int(limit)))
    max_parallel = max(1, min(16, int(max_parallel)))

    rows = get_unscored_predictions(limit=limit)
    if not rows:
        return {"ok": True, "note": "No unscored predictions found.", "requested": limit, "scored": 0}

    results: List[Dict[str, Any]] = []
    counts: Dict[str, int] = {
        "scored": 0,
        "not_matured": 0,
        "missing_asof": 0,
        "no_data": 0,
        "no_close_col": 0,
        "asof_not_found": 0,
        "error": 0,
    }

    def work(r: Dict[str, Any]):
        return _score_one_prediction_row(r, source_pref=source_pref)

    if max_parallel == 1 or len(rows) == 1:
        items = []
        for r in rows:
            try:
                items.append(work(r))
            except Exception:
                items.append((int(r["id"]), (r.get("ticker") or "").upper().strip(), _to_date_key(str(r.get("as_of_date") or "")), None, None, "error"))
    else:
        items = []
        with ThreadPoolExecutor(max_workers=max_parallel) as ex:
            futs = {ex.submit(work, r): r for r in rows}
            for fut in as_completed(futs):
                r = futs[fut]
                try:
                    items.append(fut.result())
                except Exception:
                    items.append((int(r["id"]), (r.get("ticker") or "").upper().strip(), _to_date_key(str(r.get("as_of_date") or "")), None, None, "error"))

    for pred_id, ticker, asof_key, realized_return, realized_direction, status in items:
        counts[status] = counts.get(status, 0) + 1
        if status == "scored":
            set_prediction_score(pred_id, float(realized_return), realized_direction)
        results.append({
            "id": pred_id,
            "ticker": ticker,
            "as_of_date": asof_key,
            "realized_return": json_safe(realized_return),
            "realized_direction": realized_direction,
            "status": status,
        })

    return {
        "ok": True,
        "requested": limit,
        "fetched": len(rows),
        "counts": counts,
        "sample": results[: min(25, len(results))],
        "note": "Use /api/report_card or /api/metrics once enough predictions mature.",
    }


@app.get("/api/scoreboard")
def scoreboard(ticker: str = "SPY", horizon_days: int = 5, limit: int = 200):
    t = (ticker or "").upper().strip()
    horizon_days = max(1, min(60, int(horizon_days)))
    limit = max(1, min(2000, int(limit)))

    rows = get_scoreboard(t, horizon_days=horizon_days, limit=limit)
    return {"ticker": t, "horizon_days": horizon_days, "returned": len(rows), "rows": rows}


@app.get("/api/metrics")
def metrics(ticker: str = "SPY", horizon_days: int = 5, limit: int = 500):
    t = (ticker or "").upper().strip()
    horizon_days = max(1, min(60, int(horizon_days)))
    limit = max(10, min(5000, int(limit)))

    rows = get_scoreboard(t, horizon_days=horizon_days, limit=limit)

    scored = []
    for r in rows:
        p_dir = (r.get("direction") or "").upper().strip()
        r_dir = (r.get("realized_direction") or "").upper().strip()
        prob = clamp01(r.get("prob_up"))
        rr = r.get("realized_return")
        try:
            rr = float(rr) if rr is not None else None
        except Exception:
            rr = None
        if p_dir in ("UP", "DOWN") and r_dir in ("UP", "DOWN") and prob is not None:
            scored.append((prob, p_dir, r_dir, rr))

    if not scored:
        return {
            "ticker": t,
            "horizon_days": horizon_days,
            "note": "No scored predictions yet. Run POST /api/score_predictions after some time passes.",
            "count": 0,
        }

    hits = 0
    ret_sum = 0.0
    ret_n = 0

    buckets = [
        {"label": "LOW", "lo": 0.00, "hi": 0.10, "count": 0, "hit_rate": None},
        {"label": "MEDIUM", "lo": 0.10, "hi": 0.30, "count": 0, "hit_rate": None},
        {"label": "HIGH", "lo": 0.30, "hi": 1.01, "count": 0, "hit_rate": None},
    ]

    for prob, p_dir, r_dir, rr in scored:
        if p_dir == r_dir:
            hits += 1
        if rr is not None and math.isfinite(rr):
            ret_sum += rr
            ret_n += 1

        cs = confidence_score(prob) or 0.0
        for b in buckets:
            if cs >= b["lo"] and cs < b["hi"]:
                b["count"] += 1
                b.setdefault("_hits", 0)
                if p_dir == r_dir:
                    b["_hits"] += 1
                break

    for b in buckets:
        if b["count"] > 0:
            b["hit_rate"] = b["_hits"] / b["count"]
        b.pop("_hits", None)

    return {
        "ticker": t,
        "horizon_days": horizon_days,
        "count": len(scored),
        "hit_rate": hits / max(1, len(scored)),
        "avg_realized_return": (ret_sum / ret_n) if ret_n else None,
        "by_confidence": buckets,
        "note": "More samples = more reliable. HIGH confidence should usually have higher hit rate.",
    }


@app.get("/api/report_card")
def report_card(ticker: str = "SPY", horizon_days: int = 5, limit: int = 500):
    t = (ticker or "").upper().strip()
    horizon_days = max(1, min(60, int(horizon_days)))
    limit = max(10, min(5000, int(limit)))

    m = metrics(ticker=t, horizon_days=horizon_days, limit=limit)
    if m.get("count", 0) == 0:
        return m

    hit = m.get("hit_rate")
    by_conf = m.get("by_confidence") or []
    best = None
    for b in by_conf:
        if b.get("label") == "HIGH":
            best = b

    return {
        "ticker": t,
        "horizon_days": horizon_days,
        "samples": m.get("count"),
        "overall_hit_rate": hit,
        "avg_realized_return": m.get("avg_realized_return"),
        "high_confidence": best,
        "by_confidence": by_conf,
        "how_to_read": [
            "overall_hit_rate: how often UP/DOWN matched reality for scored predictions.",
            "high_confidence: same metric but only when the model was far from 50/50.",
            "If HIGH has low samples, wait for more predictions to mature.",
        ],
    }


# -----------------------------
# run_phase2
# -----------------------------
@app.post("/api/run_phase2")
def run_phase2(req: PredictRequest):
    run_id = datetime.utcnow().strftime("%Y%m%d_%H%M%S")

    tickers_list = (
        TICKERS
        if req.all or not req.tickers
        else [t.upper().strip() for t in req.tickers if t and t.strip()]
    )

    max_parallel = max(1, int(req.max_parallel))
    horizon_days = int(req.horizon_days)
    base_weekly_move = float(req.base_weekly_move)
    retrain = bool(req.retrain)
    source_pref = (req.source_pref or "auto").lower().strip()

    create_run(run_id, total=len(tickers_list))

    results: List[Dict[str, Any]] = []
    errors: Dict[str, str] = {}
    completed = 0

    if max_parallel == 1:
        for t in tickers_list:
            try:
                results.append(_run_one_ticker(t, horizon_days, base_weekly_move, retrain=retrain, source_pref=source_pref))
            except Exception as e:
                errors[t] = str(e)
            completed += 1
            update_run_progress(run_id, completed)
    else:
        with ThreadPoolExecutor(max_workers=max_parallel) as ex:
            futs = {
                ex.submit(_run_one_ticker, t, horizon_days, base_weekly_move, retrain, source_pref): t
                for t in tickers_list
            }
            for fut in as_completed(futs):
                t = futs[fut]
                try:
                    results.append(fut.result())
                except Exception as e:
                    errors[t] = str(e)
                completed += 1
                update_run_progress(run_id, completed)

    if results:
        insert_predictions(run_id, results)

    finish_run(run_id)

    return {
        "run_id": run_id,
        "generated_at": datetime.utcnow().isoformat(timespec="seconds") + "Z",
        "status": "started",
        "total": len(tickers_list),
        "stored": len(results),
        "errors": errors,
        "horizon_days": horizon_days,
        "retrain": retrain,
        "source_pref": source_pref,
    }


@app.get("/api/run_phase2/status")
def run_status(run_id: str):
    state = get_run_state(run_id)
    if not state:
        return {"error": "run_id not found"}

    total = int(state["total"])
    completed = int(state["completed"])
    pct = round(100 * completed / max(1, total), 1)

    return {
        "run_id": run_id,
        "status": state["status"],
        "progress": {"completed": completed, "total": total, "pct": pct},
        "started_at": state["started_at"],
        "finished_at": state.get("finished_at"),
    }


# -----------------------------
# summary
# -----------------------------
def _confidence_rank(label: str) -> int:
    lab = (label or "").upper().strip()
    if lab == "HIGH":
        return 3
    if lab == "MEDIUM":
        return 2
    if lab == "LOW":
        return 1
    return 0


@app.post("/api/summary")
def summary_post(req: SummaryRequest):
    tickers_list = req.tickers or ["SPY", "QQQ", "IWM"]
    tickers_list = [t.upper().strip() for t in tickers_list if t and t.strip()]

    max_parallel = max(1, int(req.max_parallel))
    horizon_days = int(req.horizon_days)
    base_weekly_move = float(req.base_weekly_move)
    retrain = bool(req.retrain)
    source_pref = (req.source_pref or "auto").lower().strip()

    min_conf = (req.min_confidence or "").upper().strip()
    min_conf_rank = _confidence_rank(min_conf) if min_conf else 0
    min_prob_up = req.min_prob_up
    try:
        min_prob_up = float(min_prob_up) if min_prob_up is not None else None
    except Exception:
        min_prob_up = None

    results: List[Dict[str, Any]] = []
    errors: Dict[str, str] = {}

    def accept(p: Dict[str, Any]) -> bool:
        if min_conf_rank > 0:
            lab = (p.get("confidence") or "").upper().strip()
            if _confidence_rank(lab) < min_conf_rank:
                return False
        if min_prob_up is not None:
            pu = clamp01(p.get("prob_up"))
            if pu is None or pu < min_prob_up:
                return False
        return True

    if max_parallel == 1:
        for t in tickers_list:
            try:
                p = _run_one_ticker(t, horizon_days, base_weekly_move, retrain=retrain, source_pref=source_pref)
                if accept(p):
                    results.append(p)
            except Exception as e:
                errors[t] = str(e)
    else:
        with ThreadPoolExecutor(max_workers=max_parallel) as ex:
            futs = {
                ex.submit(_run_one_ticker, t, horizon_days, base_weekly_move, retrain, source_pref): t
                for t in tickers_list
            }
            for fut in as_completed(futs):
                t = futs[fut]
                try:
                    p = fut.result()
                    if accept(p):
                        results.append(p)
                except Exception as e:
                    errors[t] = str(e)

    return {
        "run_id": f"LIVE_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}",
        "generated_at": datetime.utcnow().isoformat(timespec="seconds") + "Z",
        "tickers": tickers_list,
        "horizon_days": horizon_days,
        "retrain": retrain,
        "source_pref": source_pref,
        "count": len(results),
        "min_confidence": min_conf or None,
        "min_prob_up": min_prob_up,
        "predictions": results,
        "errors": errors,
    }


@app.get("/api/summary")
def summary(limit: int = 50, run_id: Optional[str] = None):
    if run_id is None:
        run_id = get_latest_run_id()

    if not run_id:
        return {"predictions": [], "note": "No predictions yet."}

    preds = get_predictions_for_run(run_id, limit=max(1, int(limit)))

    out = []
    for p in preds:
        pu = clamp01(p.get("prob_up"))
        out.append({
            "id": p.get("id"),
            "ticker": p.get("ticker"),
            "source": p.get("source"),
            "prob_up": json_safe(pu),
            "exp_return": json_safe(p.get("exp_return")),
            "direction": p.get("direction"),
            "horizon_days": p.get("horizon_days"),
            "generated_at": p.get("generated_at"),
            "as_of_date": p.get("as_of_date"),
            "as_of_close": json_safe(p.get("as_of_close")),
            "realized_return": json_safe(p.get("realized_return")),
            "realized_direction": p.get("realized_direction"),
            "scored_at": p.get("scored_at"),
            "confidence_score": json_safe(confidence_score(pu)),
            "confidence": confidence_label(pu),
        })

    return {"run_id": run_id, "count_returned": len(out), "predictions": out}
