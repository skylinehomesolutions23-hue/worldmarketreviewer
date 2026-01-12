# build_mobile_summary.py
import os
import json
import math
import pandas as pd
from datetime import datetime
from typing import Any, Dict, List

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")

SUMMARY_JSON = os.path.join(DATA_DIR, "latest_summary.json")
SUMMARY_CSV = os.path.join(DATA_DIR, "mobile_summary.csv")

# Optional inputs (may be missing/empty)
KILL_FILE = os.path.join(DATA_DIR, "kill_switch_status.csv")
PREDICTIONS_FILE = os.path.join(BASE_DIR, "results", "predictions.csv")


def sanitize_json(obj: Any) -> Any:
    """Convert NaN/Inf to None and ensure everything is JSON-serializable."""
    if obj is None:
        return None
    if isinstance(obj, float):
        if math.isnan(obj) or math.isinf(obj):
            return None
        return obj
    if isinstance(obj, (int, bool, str)):
        return obj
    if isinstance(obj, (list, tuple)):
        return [sanitize_json(x) for x in obj]
    if isinstance(obj, dict):
        return {str(k): sanitize_json(v) for k, v in obj.items()}
    # pandas types, timestamps, etc.
    return str(obj)


def safe_read_csv(path: str) -> pd.DataFrame:
    """
    Read CSV safely.
    Returns empty DataFrame if file missing or empty or unreadable.
    """
    if not os.path.exists(path):
        return pd.DataFrame()
    try:
        # If file exists but is empty (0 bytes) this will throw; we catch below.
        if os.path.getsize(path) == 0:
            return pd.DataFrame()
    except Exception:
        return pd.DataFrame()

    try:
        return pd.read_csv(path)
    except Exception:
        return pd.DataFrame()


def file_status(path: str) -> Dict[str, Any]:
    """Human-friendly status for debugging on Render/phone."""
    if not os.path.exists(path):
        return {"exists": False}
    try:
        return {"exists": True, "bytes": os.path.getsize(path)}
    except Exception as e:
        return {"exists": True, "bytes": None, "error": str(e)}


def normalize_predictions(pred_df: pd.DataFrame) -> List[Dict[str, Any]]:
    """
    Make predictions robust across formats.
    Supports:
      - columns: ticker, prob_up (required)
      - optional: direction, asof
    If direction missing, compute from prob_up.
    """
    if pred_df is None or pred_df.empty:
        return []

    # Clean column names
    pred_df = pred_df.copy()
    pred_df.columns = [str(c).strip().lower() for c in pred_df.columns]

    # Must have ticker and prob_up to build usable predictions
    if "ticker" not in pred_df.columns or "prob_up" not in pred_df.columns:
        return []

    out = []
    for _, row in pred_df.iterrows():
        ticker = row.get("ticker")
        prob = row.get("prob_up")

        # Convert prob_up safely to float if possible
        try:
            prob_f = float(prob)
        except Exception:
            prob_f = None

        direction = row.get("direction")
        if (direction is None or str(direction).strip() == "") and prob_f is not None:
            direction = "UP" if prob_f >= 0.5 else "DOWN"

        asof = row.get("asof")
        if asof is None or str(asof).strip() == "":
            # If predictions.csv has no timestamp, stamp it now
            asof = datetime.utcnow().isoformat(timespec="seconds") + "Z"

        out.append({
            "ticker": str(ticker).strip() if ticker is not None else None,
            "prob_up": prob_f,
            "direction": str(direction).strip() if direction is not None else None,
            "asof": asof,
        })

    return out


def normalize_kill_switch(kill_df: pd.DataFrame) -> Dict[str, Any]:
    """
    Supports either:
      - key,value columns
      - or any 2-column CSV
      - or a single row with named columns
    """
    if kill_df is None or kill_df.empty:
        return {}

    df = kill_df.copy()
    df.columns = [str(c).strip().lower() for c in df.columns]

    # Common format: key,value
    if "key" in df.columns and "value" in df.columns:
        out = {}
        for _, row in df.iterrows():
            k = str(row.get("key", "")).strip()
            v = row.get("value", "")
            if k:
                out[k] = v
        return out

    # If exactly 2 columns, treat as key/value
    if len(df.columns) == 2:
        c1, c2 = df.columns[0], df.columns[1]
        out = {}
        for _, row in df.iterrows():
            k = str(row.get(c1, "")).strip()
            v = row.get(c2, "")
            if k:
                out[k] = v
        return out

    # Otherwise: return first row as dict
    return df.iloc[0].to_dict()


def main():
    os.makedirs(DATA_DIR, exist_ok=True)

    kill_df = safe_read_csv(KILL_FILE)
    pred_df = safe_read_csv(PREDICTIONS_FILE)

    predictions = normalize_predictions(pred_df)
    kill_switch = normalize_kill_switch(kill_df)

    summary = {
        "generated_at": datetime.utcnow().isoformat(timespec="seconds") + "Z",
        "system_status": "OK",
        "kill_switch": kill_switch,
        "predictions": predictions,

        # Debug section helps you instantly know what’s missing on Render
        "debug": {
            "files": {
                "kill_switch_status.csv": file_status(KILL_FILE),
                "results/predictions.csv": file_status(PREDICTIONS_FILE),
            },
            "counts": {
                "kill_rows": int(0 if kill_df is None else len(kill_df)),
                "prediction_rows": int(0 if pred_df is None else len(pred_df)),
                "prediction_items": len(predictions),
            },
            "notes": [],
        }
    }

    # Helpful notes
    if not summary["debug"]["files"]["results/predictions.csv"].get("exists"):
        summary["debug"]["notes"].append("predictions.csv missing (run Phase 2 on server or create predictions)")
    elif len(pred_df) == 0:
        summary["debug"]["notes"].append("predictions.csv exists but is empty")
    elif len(predictions) == 0:
        summary["debug"]["notes"].append("predictions.csv exists but columns not recognized (needs ticker + prob_up)")

    # Write JSON (API uses this)
    with open(SUMMARY_JSON, "w", encoding="utf-8") as f:
        json.dump(sanitize_json(summary), f, indent=2)

    # Write CSV (optional)
    try:
        pd.DataFrame(predictions).to_csv(SUMMARY_CSV, index=False)
    except Exception:
        pass

    print(f"Mobile summary written: {SUMMARY_JSON}")


if __name__ == "__main__":
    main()
