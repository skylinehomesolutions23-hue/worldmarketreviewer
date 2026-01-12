# build_mobile_summary.py
import os
import json
import pandas as pd
from datetime import datetime

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")

SUMMARY_JSON = os.path.join(DATA_DIR, "latest_summary.json")
SUMMARY_CSV = os.path.join(DATA_DIR, "mobile_summary.csv")

# Optional inputs (may be empty)
KILL_FILE = os.path.join(DATA_DIR, "kill_switch_status.csv")
PREDICTIONS_FILE = os.path.join(BASE_DIR, "results", "predictions.csv")


def safe_read_csv(path: str) -> pd.DataFrame:
    """
    Read CSV safely.
    Returns empty DataFrame if file missing or empty.
    """
    if not os.path.exists(path):
        return pd.DataFrame()
    if os.path.getsize(path) < 10:
        return pd.DataFrame()
    try:
        return pd.read_csv(path)
    except Exception:
        return pd.DataFrame()


def main():
    os.makedirs(DATA_DIR, exist_ok=True)

    kill_df = safe_read_csv(KILL_FILE)
    pred_df = safe_read_csv(PREDICTIONS_FILE)

    summary = {
        "generated_at": datetime.utcnow().isoformat(timespec="seconds") + "Z",
        "system_status": "OK",
        "kill_switch": {},
        "predictions": [],
    }

    # Kill switch info (if available)
    if not kill_df.empty:
        for _, row in kill_df.iterrows():
            k = str(row.get("key", "")).strip()
            v = str(row.get("value", "")).strip()
            if k:
                summary["kill_switch"][k] = v

    # Predictions (latest only)
    if not pred_df.empty:
        for _, row in pred_df.iterrows():
            summary["predictions"].append({
                "ticker": row.get("ticker"),
                "prob_up": row.get("prob_up"),
                "direction": row.get("direction"),
                "asof": row.get("asof"),
            })

    # Always write JSON (mobile uses this)
    with open(SUMMARY_JSON, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)

    # Optional CSV for debugging
    try:
        pd.DataFrame(summary["predictions"]).to_csv(SUMMARY_CSV, index=False)
    except Exception:
        pass

    print(f"Mobile summary written: {SUMMARY_JSON}")


if __name__ == "__main__":
    main()
