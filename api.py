import math
from datetime import datetime
from typing import List, Optional, Dict, Any
from concurrent.futures import ThreadPoolExecutor, as_completed

from fastapi import FastAPI
from fastapi.responses import Response
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

app = FastAPI(title="WorldMarketReviewer API")


# ---------------- helpers ----------------

def json_safe(x):
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


def _run_one_ticker(ticker: str, horizon_days: int, base_weekly_move: float) -> Dict[str, Any]:
    t = ticker.upper().strip()

    df = load_stock_data(t)
    if df is None or len(df) < 10:
        raise ValueError("Not enough data")

    df = build_features(df)
    feature_cols = [c for c in df.columns if c not in ["target", "date"]]

    probs = walk_forward_predict_proba(
        df,
        feature_cols=feature_cols,
        target_col="target"
    )

    prob_up = float(probs.iloc[-1])
    exp_return = compute_expected_return_from_prob(prob_up, base_weekly_move)
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
def startup():
    init_db()


# ---------------- routes ----------------

@app.get("/")
def root():
    return {"message": "WorldMarketReviewer API is running"}


@app.get("/health")
def health():
    return {
        "status": "ok",
        "service": "worldmarketreviewer",
        "version": "0.2.0",
        "time_utc": datetime.utcnow().isoformat(timespec="seconds") + "Z",
    }


@app.head("/api/summary")
def summary_head():
    return Response(status_code=200)


@app.post("/api/run_phase2")
def run_phase2(req: PredictRequest):
    run_id = datetime.utcnow().strftime("%Y%m%d_%H%M%S")

    if req.all or not req.tickers:
        tickers = TICKERS
    else:
        tickers = [t.upper().strip() for t in req.tickers if t and t.strip()]

    horizon_days = int(req.horizon_days)
    base_weekly_move = float(req.base_weekly_move)
    max_parallel = max(1, int(req.max_parallel))

    create_run(run_id, total=len(tickers))

    completed = 0
    results: List[Dict[str, Any]] = []

    if max_parallel == 1:
        for t in tickers:
            try:
                results.append(_run_one_ticker(t, horizon_days, base_weekly_move))
                completed += 1
                update_run_progress(run_id, completed)
            except Exception:
                completed += 1
                update_run_progress(run_id, completed)
    else:
        with ThreadPoolExecutor(max_workers=max_parallel) as ex:
            futures = {
                ex.submit(_run_one_ticker, t, horizon_days, base_weekly_move): t
                for t in tickers
            }
            for fut in as_completed(futures):
                try:
                    results.append(fut.result())
                except Exception:
                    pass
                completed += 1
                update_run_progress(run_id, completed)

    if results:
        insert_predictions(run_id, results)

    finish_run(run_id)

    return {
        "run_id": run_id,
        "status": "started",
        "total": len(tickers)
    }


@app.get("/api/run_phase2/status")
def run_status(run_id: str):
    state = get_run_state(run_id)
    if not state:
        return {"error": "run_id not found"}

    return {
        "run_id": run_id,
        "status": state["status"],
        "progress": {
            "completed": state["completed"],
            "total": state["total"],
            "pct": round(100 * state["completed"] / max(1, state["total"]), 1),
        },
        "started_at": state["started_at"],
        "finished_at": state["finished_at"],
    }


@app.get("/api/summary")
def summary(limit: int = 50, run_id: Optional[str] = None):
    if run_id is None:
        run_id = get_latest_run_id()

    if not run_id:
        return {
            "generated_at": datetime.utcnow().isoformat(timespec="seconds") + "Z",
            "predictions": [],
            "note": "No predictions yet. POST to /api/run_phase2 first.",
        }

    preds = get_predictions_for_run(run_id, limit=max(1, int(limit)))

    return {
        "generated_at": datetime.utcnow().isoformat(timespec="seconds") + "Z",
        "run_id": run_id,
        "predictions": [
            {
                "ticker": p["ticker"],
                "prob_up": json_safe(p["prob_up"]),
                "exp_return": json_safe(p["exp_return"]),
                "direction": p["direction"],
                "generated_at": p["generated_at"],
                "horizon_days": p["horizon_days"],
            }
            for p in preds
        ],
    }
