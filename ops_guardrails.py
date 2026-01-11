# ops_guardrails.py

import pandas as pd
import numpy as np

EQUITY_PATH = "results/portfolio_equity_final_master.csv"
MAX_VOL_SPIKE = 3.0     # std deviations
MAX_EXPOSURE = 1.0


def compute_vol(series, window=6):
    return series.pct_change().rolling(window).std()


def evaluate_guardrails() -> tuple[float, str]:
    df = pd.read_csv(EQUITY_PATH, parse_dates=["date"]).set_index("date")

    if df.empty or len(df) < 12:
        return 0.0, "INSUFFICIENT_DATA"

    returns = df["equity"].pct_change().dropna()
    vol = compute_vol(df["equity"])

    if vol.iloc[-1] > MAX_VOL_SPIKE * vol.mean():
        return 0.0, "VOL_SPIKE_FREEZE"

    if returns.isna().any():
        return 0.0, "DATA_INTEGRITY_FREEZE"

    return MAX_EXPOSURE, "GUARDRAILS_CLEAR"


if __name__ == "__main__":
    exposure, reason = evaluate_guardrails()
    print("Guardrail exposure:", exposure)
    print("Reason:", reason)
