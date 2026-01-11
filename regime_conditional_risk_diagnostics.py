import pandas as pd
import numpy as np
from pathlib import Path

from data_utils import load_price_series


# -----------------------------
# Configuration
# -----------------------------

DATA_DIR = Path("data")
RESULTS_DIR = Path("results")
OUTPUT_DIR = RESULTS_DIR / "diagnostics"

SPY_PATH = DATA_DIR / "SPY.csv"
PORTFOLIO_PATH = RESULTS_DIR / "portfolio_equity_FINAL.csv"

SPY_MA_WINDOW = 200  # regime definition

OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


# -----------------------------
# Helpers
# -----------------------------

def compute_returns(price: pd.Series) -> pd.Series:
    return price.pct_change().dropna()


def compute_regime(spy_price: pd.Series) -> pd.Series:
    ma = spy_price.rolling(SPY_MA_WINDOW).mean()
    regime = spy_price > ma
    return regime.rename("risk_on")


def rolling_beta(returns: pd.Series, benchmark: pd.Series, window: int) -> pd.Series:
    cov = returns.rolling(window).cov(benchmark)
    var = benchmark.rolling(window).var()
    return cov / var


def rolling_vol(returns: pd.Series, window: int) -> pd.Series:
    return returns.rolling(window).std() * np.sqrt(252)


def rolling_max_drawdown(price: pd.Series) -> pd.Series:
    peak = price.cummax()
    return (price / peak - 1.0).cummin()


# -----------------------------
# Main pipeline
# -----------------------------

def main():
    portfolio_price = load_price_series(PORTFOLIO_PATH)
    spy_price = load_price_series(SPY_PATH)

    prices = pd.concat(
        [portfolio_price, spy_price],
        axis=1,
        join="inner"
    )
    prices.columns = ["portfolio", "spy"]

    returns = compute_returns(prices)

    regime = compute_regime(prices["spy"])
    regime = regime.reindex(returns.index).dropna()

    returns = returns.loc[regime.index]
    prices = prices.loc[regime.index]

    diagnostics = pd.DataFrame(index=returns.index)
    diagnostics["risk_on"] = regime

    diagnostics["beta_6m"] = rolling_beta(
        returns["portfolio"],
        returns["spy"],
        126
    )

    diagnostics["vol_6m"] = rolling_vol(
        returns["portfolio"],
        126
    )

    diagnostics["drawdown"] = rolling_max_drawdown(
        prices["portfolio"]
    )

    # -----------------------------
    # Regime summaries
    # -----------------------------

    summary = (
        diagnostics
        .groupby("risk_on")
        .agg(
            avg_beta=("beta_6m", "mean"),
            avg_vol=("vol_6m", "mean"),
            worst_drawdown=("drawdown", "min"),
            obs=("beta_6m", "count")
        )
        .rename(index={True: "risk_on", False: "risk_off"})
    )

    diagnostics.to_csv(OUTPUT_DIR / "regime_conditional_risk_timeseries.csv")
    summary.to_csv(OUTPUT_DIR / "regime_conditional_risk_summary.csv")

    print("Regime-conditional diagnostics complete.")
    print(summary)


if __name__ == "__main__":
    main()
