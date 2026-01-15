import math
from datetime import datetime
from typing import List, Optional, Dict, Any
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import Response, HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
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
)

# ---------------- paths ----------------
BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"

app = FastAPI(title="WorldMarketReviewer API")

# ---------------- CORS (REQUIRED FOR PHONE) ----------------
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------- static files ----------------
if STATIC_DIR.exists():
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


def _run_one_ticker(ticker: str, horizon_days: int, base_weekly_move: float) -> Dict[str, Any]:
    t = ticker.upper().strip()

    df = load_stock_data(t)
    if df is None or len(df) < 10:
        raise ValueError(f"Not enough data for {t}")

    df = build_features(df)
    feature_cols = [c for c in df.columns if c not in ["target", "date"]]

    probs = walk_forward_predict_proba(df, feature_cols=feature_cols, target_col="target")
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
    try:
        init_db()
        print("DB init OK")
    except Exception as e:
        # IMPORTANT: do not crash server
        print("DB init FAILED:", repr(e))

# ---------------- routes ----------------
@app.get("/")
def root():
    return {"message": "WorldMarketReviewer API is running"}

@app.get("/health")
def health():
    return {
        "status": "ok",
        "service": "worldmarketreviewer",
        "version": "1.0.0",
        "time_utc": datetime.utcnow().isoformat(timespec="seconds") + "Z",
    }

# --------- MOBILE WEB (/app) ----------
@app.get("/app", response_class=HTMLResponse)
def mobile_app():
    app_file = STATIC_DIR / "app.html"
    if not app_file.exists():
        return HTMLResponse(
            content="static/app.html not found. Deploy static/app.html.",
            status_code=500,
        )
    return app_file.read_text(encoding="utf-8")

# --------- API ----------
@app.head("/api/summary")
def summary_head():
    return Response(status_code=200)

@app.post("/api/run_phase2")
def run_phase2(req: PredictRequest):
    try:
        run_id = datetime.utcnow().strftime("%Y%m%d_%H%M%S")

        if req.all or not req.tickers:
            tickers = TICKERS
        else:
            tickers = [t.upper().strip() for t in req.tickers if t]

        max_parallel = max(1, int(req.max_parallel))
        horizon_days = int(req.horizon_days)
        base_weekly_move = float(req.base_weekly_move)

        results = []
        errors = {}

        if max_parallel == 1:
            for t in tickers:
                try:
                    results.append(_run_one_ticker(t, horizon_days, base_weekly_move))
                except Exception as e:
                    errors[t] = str(e)
        else:
            with ThreadPoolExecutor(max_workers=max_parallel) as ex:
                futures = {
                    ex.submit(_run_one_ticker, t, horizon_days, base_weekly_move): t
                    for t in tickers
                }
                for fut in as_completed(futures):
                    t = futures[fut]
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

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/summary")
def summary(limit: int = 50, run_id: Optional[str] = None):
    if run_id is None:
        run_id = get_latest_run_id()

    if not run_id:
        return {
            "generated_at": datetime.utcnow().isoformat(timespec="seconds") + "Z",
            "predictions": [],
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
        "run_id": run_id,
        "predictions": out,
    }
