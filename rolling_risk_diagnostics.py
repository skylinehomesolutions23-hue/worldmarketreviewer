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

ROLLING_WINDOWS = {
    "3m": 63,
    "6m": 126,
    "12m": 252,
}

OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


# -----------------------------
# Core calculations
# -----------------------------

def compute_returns(price: pd.Series) -> pd.Series:
    return price.pct_change().dropna()


def rolling_beta(
    returns: pd.Series,
    benchmark: pd.Series,
    window: int
) -> pd.Series:
    cov = returns.rolling(window).cov(benchmark)
    var = benchmark.rolling(window).var()
    return cov / var


def rolling_vol(
    returns: pd.Series,
    window: int
) -> pd.Series:
    return returns.rolling(window).std() * np.sqrt(252)


def rolling_max_drawdown(
    price: pd.Series,
    window: int
) -> pd.Series:
    rolling_peak = price.rolling(window, min_periods=1).max()
    drawdown = price / rolling_peak - 1.0
    return drawdown.rolling(window).min()


# -----------------------------
# Main pipeline
# -----------------------------

def main():
    # Load standardized price series
    portfolio_price = load_price_series(PORTFOLIO_PATH)
    spy_price = load_price_series(SPY_PATH)

    # Align dates
    prices = pd.concat(
        [portfolio_price, spy_price],
        axis=1,
        join="inner"
    )
    prices.columns = ["portfolio", "spy"]

    # Compute returns
    returns = compute_returns(prices)

    diagnostics = pd.DataFrame(index=returns.index)

    for label, window in ROLLING_WINDOWS.items():
        diagnostics[f"beta_{label}"] = rolling_beta(
            returns["portfolio"],
            returns["spy"],
            window
        )

        diagnostics[f"vol_{label}"] = rolling_vol(
            returns["portfolio"],
            window
        )

        diagnostics[f"max_dd_{label}"] = rolling_max_drawdown(
            prices["portfolio"],
            window
        )

    # Save outputs
    diagnostics.to_csv(OUTPUT_DIR / "rolling_risk_diagnostics.csv")

    summary = diagnostics.iloc[-1].to_frame(name="latest_value")
    summary.to_csv(OUTPUT_DIR / "rolling_risk_summary.csv")

    print("Rolling risk diagnostics complete.")
    print(f"Saved to: {OUTPUT_DIR.resolve()}")


if __name__ == "__main__":
    main()
