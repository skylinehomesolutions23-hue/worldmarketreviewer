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

TAIL_Q = 0.1  # bottom 10% of SPY months


# -----------------------------
# Helpers
# -----------------------------

def compute_returns(price: pd.Series) -> pd.Series:
    return price.pct_change().dropna()


def max_drawdown(returns: pd.Series) -> float:
    cum = (1 + returns).cumprod()
    dd = cum / cum.cummax() - 1
    return dd.min()


# -----------------------------
# Main
# -----------------------------

def main():
    portfolio_price = load_price_series(PORTFOLIO_PATH)
    spy_price = load_price_series(SPY_PATH)

    port_rets = compute_returns(portfolio_price)
    spy_rets = compute_returns(spy_price)

    df = pd.DataFrame({
        "portfolio": port_rets,
        "spy": spy_rets
    }).dropna()

    tail_cutoff = df["spy"].quantile(TAIL_Q)
    tail_df = df[df["spy"] <= tail_cutoff]

    results = {
        "tail_obs": len(tail_df),
        "spy_tail_mean": tail_df["spy"].mean(),
        "portfolio_tail_mean": tail_df["portfolio"].mean(),
        "tail_corr": tail_df["portfolio"].corr(tail_df["spy"]),
        "portfolio_tail_max_dd": max_drawdown(tail_df["portfolio"])
    }

    out = pd.DataFrame([results])
    out.to_csv(DIAG_DIR / "tail_dependency_summary.csv", index=False)

    print("Tail dependency analysis complete.")
    print(out.T)


if __name__ == "__main__":
    main()
