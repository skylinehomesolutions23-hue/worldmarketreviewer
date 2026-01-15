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

# --- absolute paths (Render-safe) ---
BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"

app = FastAPI(title="WorldMarketReviewer API")

# Serve /static/* from ./static next to this file
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


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
    return {
        "status": "ok",
        "service": "worldmarketreviewer",
        "version": "0.3.0",
        "time_utc": datetime.utcnow().isoformat(timespec="seconds") + "Z",
    }


# Mobile web app (installable via Add to Home Screen)
@app.get("/app", response_class=HTMLResponse)
def mobile_app():
    app_file = STATIC_DIR / "app.html"
    if not app_file.exists():
        return HTMLResponse(
            content="static/app.html not found on server (ensure static/app.html is next to api.py).",
            status_code=500,
        )
    return app_file.read_text(encoding="utf-8")


# Avoid any weird HEAD behavior on Render / proxies
@app.head("/api/summary")
def summary_head():
    return Response(status_code=200)


@app.post("/api/run_phase2")
def run_phase2(req: PredictRequest):
    """
    Run predictions and store in DB (Supabase Postgres).
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

    # create run state (mobile polling)
    create_run(run_id, total=len(tickers))

    results: List[Dict[str, Any]] = []
    errors: Dict[str, str] = {}
    completed = 0

    if max_parallel == 1:
        for t in tickers:
            try:
                results.append(_run_one_ticker(t, horizon_days, base_weekly_move))
            except Exception as e:
                errors[t] = str(e)
            completed += 1
            update_run_progress(run_id, completed)
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
                completed += 1
                update_run_progress(run_id, completed)

    if results:
        insert_predictions(run_id, results)

    finish_run(run_id)

    return {
        "run_id": run_id,
        "status": "started",
        "total": len(tickers),
        "stored": len(results),
        "errors": errors,
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


@app.get("/api/summary")
def summary(limit: int = 50, run_id: Optional[str] = None):
    """
    Latest-run summary (clean phone output).

    - Default: returns ONLY the latest run's rows
    - Optional: pass run_id=... to view a specific run
    """
    if run_id is None:
        run_id = get_latest_run_id()

    if not run_id:
        return {
            "generated_at": datetime.utcnow().isoformat(timespec="seconds") + "Z",
            "system_status": "OK",
            "predictions": [],
            "note": "No predictions yet. POST to /api/run_phase2 first.",
        }

    preds = get_predictions_for_run(run_id, limit=max(1, int(limit)))

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
        "run_id": run_id,
        "limit": max(1, int(limit)),
        "count_returned": len(out),
        "predictions": out,
        "note": None,
    }
