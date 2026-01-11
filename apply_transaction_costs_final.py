import pandas as pd
import numpy as np
from pathlib import Path

# =========================
# FILES
# =========================
EQUITY_FILE = "results/portfolio_equity_final_master.csv"
WEIGHTS_FILE = "data/weights_monthly.csv"   # must already exist
OUTPUT_FILE = "results/portfolio_equity_final_costs.csv"

# =========================
# SETTINGS
# =========================
COST_PER_TURNOVER = 0.001  # 10 bps per 100% turnover


def main():
    eq = pd.read_csv(EQUITY_FILE, parse_dates=["date"])
    w = pd.read_csv(WEIGHTS_FILE, parse_dates=["date"])

    # -------------------------
    # Calculate turnover
    # -------------------------
    w = w.sort_values(["ticker", "date"])
    w["prev_weight"] = w.groupby("ticker")["weight"].shift(1)
    w["turnover"] = (w["weight"] - w["prev_weight"]).abs()
    turnover = w.groupby("date")["turnover"].sum()

    # -------------------------
    # Merge
    # -------------------------
    df = eq.merge(turnover, on="date", how="left")
    df["turnover"] = df["turnover"].fillna(0)

    # -------------------------
    # Apply costs
    # -------------------------
    df["cost"] = df["turnover"] * COST_PER_TURNOVER
    df["net_ret"] = df["adj_ret"] - df["cost"]

    df["equity"] = (1 + df["net_ret"]).cumprod()

    # -------------------------
    # Save
    # -------------------------
    out = df[[
        "date",
        "equity",
        "net_ret",
        "turnover",
        "cost"
    ]]

    Path(OUTPUT_FILE).parent.mkdir(exist_ok=True)
    out.to_csv(OUTPUT_FILE, index=False)

    print(f"💸 Cost-adjusted equity saved → {OUTPUT_FILE}")
    print(out.tail())


if __name__ == "__main__":
    main()
