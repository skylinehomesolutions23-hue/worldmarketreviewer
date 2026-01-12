# api.py
import math
from datetime import datetime
from typing import List, Optional, Dict, Any
from concurrent.futures import ThreadPoolExecutor, as_completed

from fastapi import FastAPI
from pydantic import BaseModel

from data_loader import load_stock_data
from feature_engineering import build_features
from walk_forward import walk_forward_predict_proba

from db import init_db, insert_predictions, get_latest_predictions
from health import check as health_check


# ---------- tickers (prefer tickers.py; fallback to main_autobatch.py) ----------
try:
    # recommended: keep tickers in a pure constants file
    from tickers import TICKERS  # type: ignore
except Exception:
    # fallback if you still keep them in main_autobatch.py
    from main_autobatch import TICKERS  # type: ignore


app = FastAPI(title="WorldMarketReviewer API")


# ---------------- helpers ----------------
def json_safe(x):
    """Convert NaN/Inf and weird values into JSON-safe primitives."""
    if x is None:
        return None
    try:
        if isinstance(x, float) and (math.isnan(x) or math.isinf(x)):
            return None
        return x
    except Exception:
        return None


def compute_expected_return_from_prob(prob_up: float, base_move: float = 0.02) -> float:
    """
    Simple expected return proxy:
    exp_return ≈ (2*prob_up - 1) * base_move
    base_move default 2% weekly move proxy.
    """
    prob_up = max(0.0, min(1.0, float(prob_up)))
    return (2.0 * prob_up - 1.0) * float(base_move)


def _run_one_ticker(ticker: str, horizon_days: int, base_weekly_move: float) -> Dict[str, Any]:
    """Compute prediction for one ticker and return a row dict for DB insert."""
    t = ticker.upper().strip()

    df = load_stock_data(t)
    if df is None or len(df) < 10:
        raise ValueError("Not enough data")

    df = build_features(df)
    feature_cols = [c for c in df.columns if c not in ["target", "date"]]

    probs = walk_forward_predict_proba(df, feature_cols=feature_cols, target_col="target")
    prob_up = float(probs.iloc[-1])

    exp_return = compute_expected_return_from_prob(prob_up, base_move=base_weekly_move)
    direction = "UP" if prob_up >= 0.5 else "DOWN"

    return {
        "ticker": t,
        "prob_up": json_safe(prob_up),
        "exp_return": json_safe(exp_return),
        "direction": direction,
        "horizon_days": int(horizon_days),
    }


# ---------------- request models ----------------
class PredictRequest(BaseModel):
    tickers: Optional[List[str]] = None
    all: bool = False
    horizon_days: int = 5
    base_weekly_move: float = 0.02
    max_parallel: int = 1


# ---------------- startup ----------------
@app.on_event("startup")
def _startup():
    init_db()


# ---------------- routes ----------------
@app.get("/")
def root():
    return {"message": "WorldMarketReviewer API is running", "tickers_count": len(TICKERS)}


@app.get("/health")
def health():
    return health_check()


@app.get("/api/health")
def api_health():
    return health_check()


@app.post("/api/run_phase2")
def run_phase2(req: PredictRequest):
    """
    Run predictions and store in SQLite.
    Use max_parallel > 1 to run tickers concurrently.
    """
    run_id = datetime.utcnow().strftime("%Y%m%d_%H%M%S")

    if req.all or not req.tickers:
        tickers = TICKERS
    else:
        tickers = [t.upper().strip() for t in req.tickers if t and t.strip()]

    max_parallel = max(1, int(req.max_parallel))
    horizon_days = int(req.horizon_days)
    base_weekly_move = float(req.base_weekly_move)

    results: List[Dict[str, Any]] = []
    errors: Dict[str, str] = {}

    if max_parallel == 1:
        for t in tickers:
            try:
                results.append(_run_one_ticker(t, horizon_days, base_weekly_move))
            except Exception as e:
                errors[t] = str(e)
    else:
        with ThreadPoolExecutor(max_workers=max_parallel) as ex:
            future_map = {
                ex.submit(_run_one_ticker, t, horizon_days, base_weekly_move): t
                for t in tickers
            }
            for fut in as_completed(future_map):
                t = future_map[fut]
                try:
                    results.append(fut.result())
                except Exception as e:
                    errors[t] = str(e)

    if results:
        insert_predictions(run_id, results)

    return {
        "run_id": run_id,
        "requested": len(tickers),
        "stored": len(results),
        "errors": errors,
    }


@app.get("/api/summary")
def summary(limit: int = 50):
    """
    Return latest predictions (JSON-safe).
    If empty, return an empty list + a hint that the client should call /api/run_phase2.
    """
    preds = get_latest_predictions(limit=limit)

    out = []
    for p in preds:
        out.append({
            "ticker": p.get("ticker"),
            "prob_up": json_safe(p.get("prob_up")),
            "exp_return": json_safe(p.get("exp_return")),
            "direction": p.get("direction"),
            "generated_at": p.get("generated_at"),
            "run_id": p.get("run_id"),
            "horizon_days": p.get("horizon_days"),
        })

    return {
        "generated_at": datetime.utcnow().isoformat(timespec="seconds") + "Z",
        "system_status": "OK",
        "predictions": out,
        "note": None if out else "No predictions yet. POST to /api/run_phase2 to generate.",
    }
