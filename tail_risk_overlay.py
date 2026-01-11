# tail_risk_overlay.py

import pandas as pd
import numpy as np

IN_FILE = "results/portfolio_equity_beta_targeted.csv"
OUT_FILE = "results/portfolio_equity_tail_risk.csv"

WINDOW = 12          # months
VOL_THRESHOLD = 0.10 # downside vol trigger
MIN_SCALE = 0.4


def main():
    df = pd.read_csv(IN_FILE)
    df["date"] = pd.to_datetime(df["date"])
    df = df.sort_values("date")

    df["ret"] = df["equity"].pct_change()

    # Downside returns only
    downside = df["ret"].where(df["ret"] < 0, 0)

    # Rolling downside volatility
    df["downside_vol"] = downside.rolling(WINDOW).std()

    # Tail risk scaling
    df["tail_scale"] = 1.0
    df.loc[df["downside_vol"] > VOL_THRESHOLD, "tail_scale"] = MIN_SCALE

    # Apply overlay
    df["adj_ret"] = df["ret"] * df["tail_scale"]
    df["equity"] = (1 + df["adj_ret"]).cumprod()

    out = df[["date", "equity", "downside_vol", "tail_scale"]]
    out.to_csv(OUT_FILE, index=False)

    print(f"🛡 Tail-risk-adjusted equity saved → {OUT_FILE}")
    print(out.tail())


if __name__ == "__main__":
    main()
