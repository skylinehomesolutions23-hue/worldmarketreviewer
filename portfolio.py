import os
import pandas as pd

RESULTS_DIR = "results"
SIGNALS_FILE = os.path.join(RESULTS_DIR, "signals.csv")
PORTFOLIO_FILE = os.path.join(RESULTS_DIR, "portfolio.csv")

MAX_POSITIONS = 10

if not os.path.exists(SIGNALS_FILE):
    raise FileNotFoundError("signals.csv not found. Run add_signals.py first.")

df = pd.read_csv(SIGNALS_FILE)

# Only trade strong signals
trade_df = df[df["signal"] == "UP"].copy()

# Limit number of positions
trade_df = trade_df.head(MAX_POSITIONS)

# Equal weight portfolio
if len(trade_df) > 0:
    trade_df["weight"] = 1.0 / len(trade_df)
else:
    trade_df["weight"] = []

portfolio = trade_df[["ticker", "weight", "prob_up"]]

portfolio.to_csv(PORTFOLIO_FILE, index=False)

print("\n=== 💼 PORTFOLIO CREATED ===\n")
print(portfolio)
print(f"\n✅ Saved to {PORTFOLIO_FILE}")
