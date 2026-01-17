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

app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


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


def _run_one_ticker(
    ticker: str,
    horizon_days: int,
    base_weekly_move: float,
    retrain: bool = True,
) -> Dict[str, Any]:
    t = ticker.upper().strip()

    df = load_stock_data(t, freq="daily", lookback_days=365 * 6)
    if df is None or len(df) < 30:
        raise ValueError("Not enough data")

    df = build_features(df, horizon_days=horizon_days)
    feature_cols = [c for c in df.columns if c not in ["target", "date"]]

    probs = walk_forward_predict_proba(
        df,
        feature_cols=feature_cols,
        target_col="target",
        ticker=t,
        retrain=retrain,
        lookback=252,
        min_train=60,
    )

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
    retrain: bool = True


class SummaryRequest(BaseModel):
    tickers: Optional[List[str]] = None
    retrain: bool = True
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
        "version": "0.4.3",
        "time_utc": datetime.utcnow().isoformat(timespec="seconds") + "Z",
    }


@app.get("/app", response_class=HTMLResponse)
def mobile_app():
    app_file = STATIC_DIR / "app.html"
    if not app_file.exists():
        return HTMLResponse("static/app.html not found.", status_code=500)
    return app_file.read_text(encoding="utf-8")


@app.head("/api/summary")
def summary_head():
    return Response(status_code=200)


@app.post("/api/run_phase2")
def run_phase2(req: PredictRequest):
    run_id = datetime.utcnow().strftime("%Y%m%d_%H%M%S")

    tickers = TICKERS if req.all or not req.tickers else [
        t.upper().strip() for t in req.tickers if t.strip()
    ]

    create_run(run_id, total=len(tickers))

    results, errors = [], {}
    completed = 0

    for t in tickers:
        try:
            results.append(
                _run_one_ticker(
                    t,
                    horizon_days=req.horizon_days,
                    base_weekly_move=req.base_weekly_move,
                    retrain=req.retrain,
                )
            )
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


@app.post("/api/summary")
def summary_post(req: SummaryRequest):
    results, errors = [], {}

    for t in req.tickers or ["SPY", "QQQ", "IWM"]:
        try:
            results.append(
                _run_one_ticker(
                    t,
                    horizon_days=req.horizon_days,
                    base_weekly_move=req.base_weekly_move,
                    retrain=req.retrain,
                )
            )
        except Exception as e:
            errors[t] = str(e)

    return {
        "run_id": f"LIVE_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}",
        "generated_at": datetime.utcnow().isoformat(timespec="seconds") + "Z",
        "predictions": results,
        "errors": errors,
    }


@app.get("/api/summary")
def summary(
    limit: int = 50,
    run_id: Optional[str] = None,
    tickers: Optional[str] = None,
    retrain: int = 1,
    horizon_days: int = 5,  # ✅ FIXED
):
    generated_at = datetime.utcnow().isoformat(timespec="seconds") + "Z"

    # LIVE mode
    if tickers:
        results, errors = [], {}
        for t in tickers.split(","):
            try:
                results.append(
                    _run_one_ticker(
                        t.strip(),
                        horizon_days=horizon_days,
                        base_weekly_move=0.02,
                        retrain=bool(retrain),
                    )
                )
            except Exception as e:
                errors[t] = str(e)

        return {
            "generated_at": generated_at,
            "run_id": f"LIVE_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}",
            "predictions": results,
            "errors": errors,
        }

    # DB mode
    if run_id is None:
        run_id = get_latest_run_id()

    if not run_id:
        return {"generated_at": generated_at, "predictions": []}

    preds = get_predictions_for_run(run_id, limit=max(1, int(limit)))

    return {
        "generated_at": generated_at,
        "run_id": run_id,
        "predictions": [
            {
                "ticker": p.get("ticker"),
                "prob_up": json_safe(p.get("prob_up")),
                "exp_return": json_safe(p.get("exp_return")),
                "direction": p.get("direction"),
                "horizon_days": p.get("horizon_days"),
            }
            for p in preds
        ],
    }
