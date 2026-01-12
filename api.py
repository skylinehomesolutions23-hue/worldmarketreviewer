# api.py
import math
from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import FastAPI
from pydantic import BaseModel

from tickers import TICKERS
from data_loader import load_stock_data
from feature_engineering import build_features
from walk_forward import walk_forward_predict_proba
from db import init_db, insert_predictions, get_latest_predictions

app = FastAPI(title="WorldMarketReviewer API")


# ---------- helpers ----------
def json_safe(x):
    """Convert NaN/Inf into JSON-safe primitives (FastAPI rejects them)."""
    if x is None:
        return None
    try:
        if isinstance(x, float) and (math.isnan(x) or math.isinf(x)):
            return None
        return x
    except Exception:
        return None


def compute_expected_return_from_prob(prob_up: float, base_move: float = 0.02) -> float:
    prob_up = max(0.0, min(1.0, float(prob_up)))
    return (2.0 * prob_up - 1.0) * float(base_move)


# ---------- request models ----------
class PredictRequest(BaseModel):
    tickers: Optional[List[str]] = None
    all: bool = False
    force: bool = True  # reserved for future state logic
    horizon_days: int = 5
    base_weekly_move: float = 0.02


# ---------- startup ----------
@app.on_event("startup")
def _startup():
    init_db()


# ---------- routes ----------
@app.get("/")
def root():
    return {"message": "WorldMarketReviewer API is running", "tickers_count": len(TICKERS)}


@app.post("/api/run_phase2")
def run_phase2(req: PredictRequest):
    """
    Runs predictions and stores them in SQLite.
    Works on Render because data_loader falls back to online price fetch.
    """
    run_id = datetime.utcnow().strftime("%Y%m%d_%H%M%S")

    if req.all or not req.tickers:
        tickers = TICKERS
    else:
        tickers = [t.upper().strip() for t in req.tickers if t.strip()]

    results: List[Dict[str, Any]] = []
    errors: Dict[str, str] = {}

    for ticker in tickers:
        try:
            df = load_stock_data(ticker)
            if df is None or len(df) < 10:
                errors[ticker] = "Not enough data"
                continue

            df = build_features(df)
            feature_cols = [c for c in df.columns if c not in ["target", "date"]]

            probs = walk_forward_predict_proba(df, feature_cols=feature_cols, target_col="target")
            prob_up = float(probs.iloc[-1])

            exp_return = compute_expected_return_from_prob(prob_up, base_move=req.base_weekly_move)
            direction = "UP" if prob_up >= 0.5 else "DOWN"

            results.append({
                "ticker": ticker,
                "prob_up": json_safe(prob_up),
                "exp_return": json_safe(exp_return),
                "direction": direction,
                "horizon_days": int(req.horizon_days),
            })

        except Exception as e:
            errors[ticker] = str(e)

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
    }
