import pandas as pd
import numpy as np
from pathlib import Path

from data_utils import load_price_series


# -----------------------------
# Config
# -----------------------------

RESULTS_DIR = Path("results")
DIAG_DIR = RESULTS_DIR / "diagnostics"
DIAG_DIR.mkdir(parents=True, exist_ok=True)

PORTFOLIO_PATH = RESULTS_DIR / "portfolio_equity_FINAL.csv"
SPY_PATH = RESULTS_DIR / "equity_vs_spy.csv"

WINDOW = 252      # 12m rolling
STABILITY_WINDOW = 60  # 5y monthly smoothing


# -----------------------------
# Helpers
# -----------------------------

def compute_returns(price: pd.Series) -> pd.Series:
    return price.pct_change().dropna()


def rolling_beta(port_rets, bench_rets, window):
    cov = port_rets.rolling(window).cov(bench_rets)
    var = bench_rets.rolling(window).var()
    return cov / var


def rolling_vol(returns, window):
    return returns.rolling(window).std() * np.sqrt(252)


# -----------------------------
# Main
# -----------------------------

def main():
    portfolio_price = load_price_series(PORTFOLIO_PATH)
    spy_price = load_price_series(SPY_PATH)

    port_ret_
