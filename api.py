import math
from datetime import datetime
from typing import List, Optional, Dict, Any, Tuple
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import Response, HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from main_autobatch import TICKERS
from data_loader import load_stock_data
from feature_engineering import build_features
from walk_forward import walk_forward_predict_proba

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


def _to_date_key(s: str) -> str:
    """
    Normalize various datetime string formats to YYYY-MM-DD for matching.
    """
    s = (s or "").strip()
    if not s:
        return ""
    # common: "2026-01-16 05:00:00+00:00" -> "2026-01-16"
    if len(s) >= 10 and s[4] == "-" and s[7] == "-":
        return s[:10]
    return s


def _load_prices(
    ticker: str,
    freq: str = "daily",
    lookback_days: int = 365 * 6,
    source_pref: str = "auto",
) -> Any:
    """
    Wrapper around load_stock_data that *tries* to respect a requested source.
    If your load_stock_data doesn't support source selection, we fall back safely.

    source_pref:
      - "auto" (default)
      - "cache" / "yfinance" (only if your loader supports it)
    """
    t = (ticker or "").upper().strip()
    source_pref = (source_pref or "auto").lower().strip()

    try:
        return load_stock_data(t, freq=freq, lookback_days=int(lookback_days), source=source_pref)
    except TypeError:
        return load_stock_data(t, freq=freq, lookback_days=int(lookback_days))


def _find_close_col(df) -> Optional[str]:
    if df is None or getattr(df, "empty", True):
        return None

    for c in ["close", "Close", "adj_close", "Adj Close", "adjclose", "AdjClose", "Price"]:
        if c in df.columns:
            return c

    # last resort: first numeric-ish column
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
    """
    Returns (as_of_date_str, as_of_close, close_col)
    """
    payload = _sparkline_from_df(df, n=3)
    closes = payload.get("closes") or []
    dates = payload.get("dates") or []
    if not closes or not dates:
        return None, None, payload.get("close_col")
    return dates[-1], closes[-1], payload.get("close_col")


def _run_one_ticker(
    ticker: str,
    horizon_days: int,
    base_weekly_move: float,
    retrain: bool = True,
) -> Dict[str, Any]:
    t = ticker.upper().strip()

    df = _load_prices(t, freq="daily", lookback_days=365 * 6, source_pref="auto")
    if df is None or len(df) < 30:
        raise ValueError("Not enough data")

    source = df.attrs.get("source", "unknown")

    # Store as-of snapshot for later scoring
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
    }


def _score_one_prediction_row(row: Dict[str, Any], source_pref: str = "auto") -> Tuple[int, str, str, Optional[float], Optional[str], str]:
    """
    Returns: (id, ticker, as_of_date_key, realized_return, realized_direction, status)
    status:
      - "scored"
      - "not_matured" (not enough future days yet)
      - "missing_asof"
      - "no_data"
      - "no_close_col"
      - "asof_not_found"
    """
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

    # Build normalized date keys for the index
    try:
        idx_strs = [str(x) for x in df.index]
    except Exception:
        return pred_id, ticker, as_of_key, None, None, "no_data"

    idx_keys = [_to_date_key(s) for s in idx_strs]

    try:
        pos = idx_keys.index(as_of_key)
    except ValueError:
        # allow near-match: if as_of_key is not found, try last available date <= as_of_key (rare)
        # (we keep it simple: fail)
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


class PredictRequest(BaseModel):
    tickers: Optional[List[str]] = None
    all: bool = False
    horizon_days: int = 5
    base_weekly_move: float = 0.02
    max_parallel: int = 1
    retrain: bool = True


class SummaryRequest(BaseModel):
    tickers: Optional[List[str]] = None
    retrain: bool = True
    horizon_days: int = 5
    base_weekly_move: float = 0.02
    max_parallel: int = 1


@app.on_event("startup")
def _startup():
    init_db()


@app.get("/health")
def health():
    return {
        "status": "ok",
        "service": "worldmarketreviewer",
        "version": "0.8.0",
        "time_utc": datetime.utcnow().isoformat(timespec="seconds") + "Z",
    }


@app.get("/api/data_sources")
def data_sources():
    return {
        "default": "auto",
        "supported_preferences": ["auto", "cache", "yfinance"],
        "note": (
            "Some endpoints accept source_pref. If your load_stock_data does not support "
            "explicit source selection, the server will ignore it and use its normal behavior."
        ),
    }


@app.get("/api/explain")
def explain():
    return {
        "what_this_app_does": (
            "For each ticker, the backend downloads daily prices, builds features, and uses a "
            "walk-forward RandomForest model to estimate the probability the price will be higher "
            "after N trading days (horizon_days)."
        ),
        "fields": {
            "direction": "UP means prob_up >= 0.50, DOWN means prob_up < 0.50.",
            "prob_up": "Probability (0–1) the price will be up after the horizon. Not a guarantee.",
            "exp_return": "A simple proxy derived from prob_up. Educational only.",
            "horizon_days": "How many trading days ahead the prediction targets (e.g., 5).",
            "source": "Where the price data came from (cache/yfinance), if provided.",
            "as_of_date": "The last price date used when generating that prediction.",
            "scoring": "Later, we check what actually happened after horizon_days and compute accuracy.",
        },
        "important": [
            "Markets are uncertain. 100% accuracy is impossible.",
            "The goal is measurable edge + transparency, not certainty.",
        ],
    }


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
def debug_prices(ticker: str = "SPY", freq: str = "daily", lookback_days: int = 365 * 6):
    t = (ticker or "").upper().strip()
    df = _load_prices(t, freq=freq, lookback_days=int(lookback_days), source_pref="auto")
    if df is None or df.empty:
        return {"ticker": t, "ok": False, "note": "load_stock_data returned None/empty."}

    return {
        "ticker": t,
        "ok": True,
        "freq": freq,
        "source": df.attrs.get("source", "unknown"),
        "rows": int(len(df)),
        "start": str(df.index.min()),
        "end": str(df.index.max()),
        "cols": list(df.columns),
        "tail": df.tail(3).reset_index().to_dict(orient="records"),
    }


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
        return {"ticker": t, "ok": False, "note": "No data returned."}

    payload = _sparkline_from_df(df, n=max(n, horizon_days + 2))
    closes = payload.get("closes") or []
    dates = payload.get("dates") or []

    if len(closes) < horizon_days + 2:
        return {
            "ticker": t,
            "ok": False,
            "note": "Not enough closes to compute horizon return.",
            "rows": payload.get("rows", int(len(df))),
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


@app.post("/api/score_predictions")
def score_predictions(limit: int = 200, max_parallel: int = 4, source_pref: str = "auto"):
    """
    Scores stored predictions that have as_of_date but haven't been scored yet.
    It computes realized return after horizon_days trading days.
    """
    limit = max(1, min(2000, int(limit)))
    max_parallel = max(1, min(16, int(max_parallel)))

    rows = get_unscored_predictions(limit=limit)
    if not rows:
        return {"ok": True, "note": "No unscored predictions found.", "requested": limit, "scored": 0}

    results: List[Dict[str, Any]] = []
    counts: Dict[str, int] = {"scored": 0, "not_matured": 0, "missing_asof": 0, "no_data": 0, "no_close_col": 0, "asof_not_found": 0, "error": 0}

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
        "note": "Use /api/metrics to see hit-rate and calibration once enough predictions mature.",
    }


@app.get("/api/scoreboard")
def scoreboard(ticker: str = "SPY", horizon_days: int = 5, limit: int = 200):
    t = (ticker or "").upper().strip()
    horizon_days = max(1, min(60, int(horizon_days)))
    limit = max(1, min(2000, int(limit)))

    rows = get_scoreboard(t, horizon_days=horizon_days, limit=limit)
    return {
        "ticker": t,
        "horizon_days": horizon_days,
        "returned": len(rows),
        "rows": rows,
    }


@app.get("/api/metrics")
def metrics(ticker: str = "SPY", horizon_days: int = 5, limit: int = 500):
    """
    Returns accuracy metrics for scored predictions:
      - hit_rate: % where predicted direction matches realized_direction
      - avg_realized_return
      - calibration buckets of prob_up
    """
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
            "note": "No scored predictions yet. Run /api/score_predictions after some time passes.",
            "count": 0,
        }

    hits = 0
    ret_sum = 0.0
    ret_n = 0

    # calibration buckets: [0.50-0.55), [0.55-0.60), ... [0.80-1.00]
    bucket_edges = [0.50, 0.55, 0.60, 0.65, 0.70, 0.75, 0.80, 1.01]
    buckets = []
    for i in range(len(bucket_edges) - 1):
        lo = bucket_edges[i]
        hi = bucket_edges[i + 1]
        buckets.append({"lo": lo, "hi": hi, "count": 0, "up_rate": None})

    for prob, p_dir, r_dir, rr in scored:
        if (p_dir == r_dir):
            hits += 1
        if rr is not None and math.isfinite(rr):
            ret_sum += rr
            ret_n += 1
        # bucket by prob_up (only meaningful >=0.5 for "UP confidence")
        for b in buckets:
            if prob >= b["lo"] and prob < b["hi"]:
                b["count"] += 1
                b.setdefault("_up", 0)
                if r_dir == "UP":
                    b["_up"] += 1
                break

    for b in buckets:
        if b["count"] > 0:
            b["up_rate"] = b["_up"] / b["count"]
        b.pop("_up", None)

    return {
        "ticker": t,
        "horizon_days": horizon_days,
        "count": len(scored),
        "hit_rate": hits / max(1, len(scored)),
        "avg_realized_return": (ret_sum / ret_n) if ret_n else None,
        "calibration": buckets,
        "note": (
            "hit_rate is direction accuracy. calibration shows observed UP frequency by prob bucket. "
            "More samples = more reliable."
        ),
    }


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

    create_run(run_id, total=len(tickers_list))

    results: List[Dict[str, Any]] = []
    errors: Dict[str, str] = {}
    completed = 0

    if max_parallel == 1:
        for t in tickers_list:
            try:
                results.append(_run_one_ticker(t, horizon_days, base_weekly_move, retrain=retrain))
            except Exception as e:
                errors[t] = str(e)
            completed += 1
            update_run_progress(run_id, completed)
    else:
        with ThreadPoolExecutor(max_workers=max_parallel) as ex:
            futs = {
                ex.submit(_run_one_ticker, t, horizon_days, base_weekly_move, retrain): t
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


@app.post("/api/summary")
def summary_post(req: SummaryRequest):
    tickers_list = req.tickers or ["SPY", "QQQ", "IWM"]
    tickers_list = [t.upper().strip() for t in tickers_list if t and t.strip()]

    max_parallel = max(1, int(req.max_parallel))
    horizon_days = int(req.horizon_days)
    base_weekly_move = float(req.base_weekly_move)
    retrain = bool(req.retrain)

    results: List[Dict[str, Any]] = []
    errors: Dict[str, str] = {}

    if max_parallel == 1:
        for t in tickers_list:
            try:
                results.append(_run_one_ticker(t, horizon_days, base_weekly_move, retrain=retrain))
            except Exception as e:
                errors[t] = str(e)
    else:
        with ThreadPoolExecutor(max_workers=max_parallel) as ex:
            futs = {
                ex.submit(_run_one_ticker, t, horizon_days, base_weekly_move, retrain): t
                for t in tickers_list
            }
            for fut in as_completed(futs):
                t = futs[fut]
                try:
                    results.append(fut.result())
                except Exception as e:
                    errors[t] = str(e)

    return {
        "run_id": f"LIVE_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}",
        "generated_at": datetime.utcnow().isoformat(timespec="seconds") + "Z",
        "tickers": tickers_list,
        "horizon_days": horizon_days,
        "retrain": retrain,
        "count": len(results),
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

    return {
        "run_id": run_id,
        "count_returned": len(preds),
        "predictions": [
            {
                "id": p.get("id"),
                "ticker": p.get("ticker"),
                "source": p.get("source"),
                "prob_up": json_safe(p.get("prob_up")),
                "exp_return": json_safe(p.get("exp_return")),
                "direction": p.get("direction"),
                "horizon_days": p.get("horizon_days"),
                "generated_at": p.get("generated_at"),
                "as_of_date": p.get("as_of_date"),
                "as_of_close": json_safe(p.get("as_of_close")),
                "realized_return": json_safe(p.get("realized_return")),
                "realized_direction": p.get("realized_direction"),
                "scored_at": p.get("scored_at"),
            }
            for p in preds
        ],
    }
