import math
from datetime import datetime
from typing import List, Optional, Dict, Any
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


def _load_prices(
    ticker: str,
    freq: str = "daily",
    lookback_days: int = 365 * 6,
    source_pref: str = "auto",
) -> Any:
    """
    Wrapper around load_stock_data that *tries* to respect a requested source.
    Your current load_stock_data may not support this; if not, we fall back safely.

    source_pref:
      - "auto" (default)
      - "cache" / "yfinance" / "stooq" etc (only if your loader supports it)
    """
    t = (ticker or "").upper().strip()
    source_pref = (source_pref or "auto").lower().strip()

    # Try passing a source preference if the loader supports it.
    try:
        return load_stock_data(t, freq=freq, lookback_days=int(lookback_days), source=source_pref)
    except TypeError:
        # Loader doesn't accept a "source" kwarg; ignore preference.
        return load_stock_data(t, freq=freq, lookback_days=int(lookback_days))


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

    df = build_features(df, horizon_days=horizon_days)
    feature_cols = [c for c in df.columns if c not in ["target", "date"]]

    probs = walk_forward_predict_proba(
        df,
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
    }


def _sparkline_from_df(df, n: int) -> Dict[str, Any]:
    """
    Convert a price dataframe to sparkline-friendly arrays.
    """
    if df is None or df.empty:
        return {"closes": [], "dates": [], "rows": 0, "source": "unknown"}

    close_col = None
    for c in ["close", "Close", "adj_close", "Adj Close", "adjclose", "AdjClose", "Price"]:
        if c in df.columns:
            close_col = c
            break

    if close_col is None:
        for c in df.columns:
            try:
                sample = df[c].dropna().iloc[:3].tolist()
                if sample and all(isinstance(v, (int, float)) for v in sample):
                    close_col = c
                    break
            except Exception:
                continue

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
    # return (b/a - 1) if a is valid and non-zero
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
        "version": "0.7.0",
        "time_utc": datetime.utcnow().isoformat(timespec="seconds") + "Z",
    }


@app.get("/api/data_sources")
def data_sources():
    """
    Explains what we can/can't guarantee about data source selection.
    NOTE: actual enforcement depends on load_stock_data implementation.
    """
    return {
        "default": "auto",
        "supported_preferences": ["auto", "cache", "yfinance"],
        "note": (
            "This API accepts source_pref on some endpoints. "
            "If your load_stock_data implementation does not support source selection, "
            "the server will ignore it and use its normal behavior."
        ),
    }


@app.get("/api/explain")
def explain():
    """
    Beginner-friendly glossary for what the app is doing.
    """
    return {
        "what_this_app_does": (
            "For each ticker, it downloads daily price history, builds features, "
            "and uses a walk-forward RandomForest model to estimate the probability "
            "the price will be higher after N days (horizon_days)."
        ),
        "fields": {
            "direction": "UP means prob_up >= 0.50, DOWN means prob_up < 0.50.",
            "prob_up": "Model-estimated probability (0 to 1) that price will be up after the horizon.",
            "exp_return": (
                "A simple expected-return proxy derived from prob_up. "
                "It is NOT a guarantee and not the same as a brokerage forecast."
            ),
            "horizon_days": "How many trading days ahead the prediction targets (e.g., 5).",
            "source": "Where price data came from (e.g., cache/yfinance), if provided by the loader.",
        },
        "how_to_use_it": [
            "Treat prob_up as confidence, not certainty (0.55 is mild, 0.70 is stronger).",
            "Compare multiple tickers; use sorting/filtering to focus on strongest signals.",
            "Use /api/verify to manually sanity-check what prices have been doing recently.",
        ],
        "important": [
            "Predictions can be wrong. Markets are noisy.",
            "This is educational tooling, not financial advice.",
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
        return {
            "ticker": t,
            "n": n,
            "closes": [],
            "dates": [],
            "ok": False,
            "note": "No data returned by load_stock_data.",
        }

    payload = _sparkline_from_df(df, n=n)
    closes = payload.get("closes", [])[-n:]
    dates = payload.get("dates", [])[-n:]

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
            return t, None, "No data returned by load_stock_data."
        payload = _sparkline_from_df(df, n=n)
        closes = payload.get("closes", [])[-n:]
        dates = payload.get("dates", [])[-n:]
        if len(closes) < 2:
            return t, None, "Not enough valid close values."
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
    """
    Manual sanity-check endpoint for beginners.

    Returns recent closes + realized return over the last horizon_days.
    This is NOT a stored backtest of the model prediction from that past date.
    It simply answers: "What did price do over the last H days into today?"
    """
    t = (ticker or "").upper().strip()
    horizon_days = max(1, min(60, int(horizon_days)))
    n = max(10, min(365, int(n)))
    lookback_days = max(n + horizon_days + 5, min(365 * 6, int(lookback_days)))

    df = _load_prices(t, freq="daily", lookback_days=lookback_days, source_pref=source_pref)
    if df is None or df.empty:
        return {"ticker": t, "ok": False, "note": "No data returned by load_stock_data."}

    payload = _sparkline_from_df(df, n=max(n, horizon_days + 2))
    closes = payload.get("closes", [])
    dates = payload.get("dates", [])

    if len(closes) < horizon_days + 2:
        return {
            "ticker": t,
            "ok": False,
            "note": "Not enough closes to compute horizon return.",
            "rows": payload.get("rows", int(len(df))),
        }

    # last move into today over horizon_days
    last_close = closes[-1]
    prev_close = closes[-2]
    start_h_close = closes[-(horizon_days + 1)]

    ret_1d = _pct_change(prev_close, last_close)
    ret_h = _pct_change(start_h_close, last_close)
    dir_1d = "UP" if (ret_1d is not None and ret_1d >= 0) else "DOWN"
    dir_h = "UP" if (ret_h is not None and ret_h >= 0) else "DOWN"

    # return last n points for display
    closes_n = closes[-n:]
    dates_n = dates[-n:]

    return {
        "ticker": t,
        "ok": True,
        "horizon_days": horizon_days,
        "source": payload.get("source", df.attrs.get("source", "unknown")),
        "close_col": payload.get("close_col"),
        "last": {
            "close": last_close,
            "date": dates[-1] if dates else "",
        },
        "realized": {
            "return_1d": json_safe(ret_1d),
            "direction_1d": dir_1d,
            "return_horizon": json_safe(ret_h),
            "direction_horizon": dir_h,
            "horizon_start_close": start_h_close,
            "horizon_start_date": dates[-(horizon_days + 1)] if dates else "",
        },
        "series": {
            "n": len(closes_n),
            "closes": closes_n,
            "dates": dates_n,
        },
        "note": (
            "This endpoint shows realized past returns into the most recent close. "
            "It does not reconstruct what the model predicted on that past date unless you store predictions-by-date."
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
                "ticker": p.get("ticker"),
                "source": p.get("source"),
                "prob_up": json_safe(p.get("prob_up")),
                "exp_return": json_safe(p.get("exp_return")),
                "direction": p.get("direction"),
                "horizon_days": p.get("horizon_days"),
                "generated_at": p.get("generated_at"),
            }
            for p in preds
        ],
    }
