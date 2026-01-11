import os
import time
import pandas as pd

from data_loader import load_stock_data
from feature_engineering import build_features
from walk_forward import walk_forward_predict_proba

# -----------------------------
# UNIVERSE
# -----------------------------
CORE_TICKERS = [
    "AAPL", "MSFT", "GOOGL", "AMZN", "META",
    "TSLA", "NVDA", "NFLX", "AMD", "INTC",
    "JPM", "BAC", "GS", "MS", "XOM",
    "CVX", "SPY", "QQQ", "DIA"
]

LIQUID_STOCKS = [
    "ORCL", "IBM", "CRM", "ADBE",
    "WMT", "COST", "HD",
    "PFE", "JNJ", "UNH",
    "BA", "CAT", "GE"
]

SECTOR_ETFS = [
    "XLK", "XLF", "XLE", "XLV",
    "XLI", "XLY", "XLP", "XLU"
]

# 🔑 FINAL UNIVERSE (order preserved, no duplicates)
TICKERS = list(dict.fromkeys(
    CORE_TICKERS + LIQUID_STOCKS + SECTOR_ETFS
))

# -----------------------------
# FILES
# -----------------------------
RESULTS_DIR = "results"
RESULTS_FILE = os.path.join(RESULTS_DIR, "predictions.csv")
os.makedirs(RESULTS_DIR, exist_ok=True)

# -----------------------------
# RESUME LOGIC
# -----------------------------
if os.path.exists(RESULTS_FILE):
    results_df = pd.read_csv(RESULTS_FILE)
    completed = set(results_df["ticker"])
else:
    results_df = pd.DataFrame(columns=["ticker", "prob_up"])
    completed = set()

print("\n=== 🚀 AUTO-BATCH STOCK RANKER STARTED ===\n")

# -----------------------------
# MAIN LOOP
# -----------------------------
for i, ticker in enumerate(TICKERS, start=1):
    if ticker in completed:
        print(f"[SKIP] {ticker} already processed")
        continue

    print(f"[{i}/{len(TICKERS)}] Running model for: {ticker}")

    try:
        df = load_stock_data(ticker)
        df = build_features(df)

        feature_cols = [c for c in df.columns if c != "target"]

        probs = walk_forward_predict_proba(
            df,
            feature_cols=feature_cols,
            target_col="target",
        )

        prob_up = float(probs.iloc[-1])
        direction = "UP" if prob_up >= 0.5 else "DOWN"

        print(f"✔ {ticker}: {direction} ({prob_up:.2%})")

        results_df.loc[len(results_df)] = [ticker, prob_up]
        results_df.to_csv(RESULTS_FILE, index=False)

        # CPU cooldown
        time.sleep(1)

    except Exception as e:
        print(f"❌ {ticker} failed: {e}")

print("\n=== ✅ ALL TICKERS COMPLETE ===")
