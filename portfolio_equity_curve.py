import pandas as pd
import numpy as np
import os

RETURNS_FILE = "data/forward_returns.csv"
OUT_FILE = "results/portfolio_equity.csv"

TARGET_VOL = 0.10        # 10% annual vol target
MAX_LEVERAGE = 1.5
DD_REDUCE = -0.20        # reduce exposure
DD_STOP = -0.35          # go to cash


def main():
    df = pd.read_csv(RETURNS_FILE, parse_dates=["date"])
    df = df.sort_values("date")

    # Average cross-sectional return each month
    monthly = df.groupby("date")["forward_return"].mean().to_frame("raw_return")

    # Rolling volatility (12m)
    monthly["rolling_vol"] = (
        monthly["raw_return"]
        .rolling(12)
        .std()
        * np.sqrt(12)
    )

    # Volatility scaler
    monthly["vol_scalar"] = TARGET_VOL / monthly["rolling_vol"]
    monthly["vol_scalar"] = monthly["vol_scalar"].clip(0, MAX_LEVERAGE)
    monthly["vol_scalar"] = monthly["vol_scalar"].fillna(1.0)

    # Apply vol targeting
    monthly["scaled_return"] = monthly["raw_return"] * monthly["vol_scalar"]

    # Equity + drawdown
    equity = []
    drawdowns = []

    eq = 1.0
    peak = 1.0

    for r in monthly["scaled_return"]:
        eq *= (1 + r)
        peak = max(peak, eq)
        dd = eq / peak - 1

        equity.append(eq)
        drawdowns.append(dd)

    monthly["equity"] = equity
    monthly["drawdown"] = drawdowns

    # Drawdown-based exposure control
    exposure = []
    for dd in monthly["drawdown"]:
        if dd < DD_STOP:
            exposure.append(0.0)
        elif dd < DD_REDUCE:
            exposure.append(0.5)
        else:
            exposure.append(1.0)

    monthly["exposure"] = exposure

    # FINAL return that actually compounds
    monthly["final_return"] = monthly["scaled_return"] * monthly["exposure"]

    # Recompute equity using FINAL returns
    eq = 1.0
    equity_final = []
    for r
