# main_autobatch.py
import os
import time
import pandas as pd

from data_loader import load_stock_data
from feature_engineering import build_features
from walk_forward import walk_forward_predict_proba

# ✅ Default ticker list (safe for other modules to import)
TICKERS = [
    "AMZN","META","TSLA","NVDA","NFLX","AMD","INTC","JPM","BAC","GS",
    "MS","XOM","CVX","SPY","QQQ","DIA","ORCL","IBM","CRM","ADBE","WMT",
    "COST","HD","PFE","JNJ","UNH","BA","CAT","GE","XLK","XLF","XLE",
    "XLV","XLI","XLY","XLP","XLU"
]

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
RESULTS_DIR = os.path.join(BASE_DIR, "results")
RESULTS_FILE = os.path.join(RESULTS_DIR, "predictions.csv")


def main():
    os.makedirs(RESULTS_DIR, exist_ok=True)

    # Load existing results if present
    if os.path.exists(RESULTS_FILE) and os.path.getsize(RESULTS_FILE) > 10:
        results_df = pd.read_csv(RESULTS_FILE)
        if "ticker" in results_df.columns:
            completed = set(results_df["ticker"].astype(str).str.upper().str.strip())
        else:
            completed = set()
    else:
        results_df = pd.DataFrame(columns=["ticker", "prob_up", "direction", "asof"])
        completed = set()

    print("\n=== PHASE 2: BASELINE AUTO-BATCH STARTED ===\n")

    for i, ticker in enumerate(TICKERS, start=1):
        t = ticker.upper().strip()
        if t in completed:
            print(f"[SKIP] {t} already processed")
            continue

        print(f"[{i}/{len(TICKERS)}] Running model for: {t}")

        try:
            df = load_stock_data(t)
            if df is None or len(df) < 10:
                raise ValueError(f"Not enough data for {t}")

            df = build_features(df)
            feature_cols = [c for c in df.columns if c not in ["target", "date"]]

            probs = walk_forward_predict_proba(df, feature_cols=feature_cols, target_col="target")
            prob_up = float(probs.iloc[-1])
            direction = "UP" if prob_up >= 0.5 else "DOWN"

            print(f"✔ {t}: {direction} ({prob_up:.2%})")

            row = {
                "ticker": t,
                "prob_up": prob_up,
                "direction": direction,
                "asof": pd.Timestamp.utcnow().isoformat()
            }

            # Ensure columns exist
            for col in row.keys():
                if col not in results_df.columns:
                    results_df[col] = None

            results_df.loc[len(results_df)] = row
            results_df.to_csv(RESULTS_FILE, index=False)
            time.sleep(0.2)

        except Exception as e:
            print(f"❌ {t} failed: {e}")

    print("\n=== COMPLETE ===")


if __name__ == "__main__":
    main()
