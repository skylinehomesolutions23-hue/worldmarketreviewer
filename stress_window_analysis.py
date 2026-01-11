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

PORTFOLIO_PATH = RESULTS_DIR / "portfolio_equity_FINAL.csv"

OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# Named stress windows
STRESS_WINDOWS = {
    "GFC_2008": ("2008-09-01", "2009-06-30"),
    "COVID_2020": ("2020-02-01", "2020-05-31"),
    "RATE_SHOCK_2022": ("2022-01-01", "2022-10-31"),
}


# -----------------------------
# Helpers
# -----------------------------

def compute_returns(price: pd.Series) -> pd.Series:
    return price.pct_change().dropna()


def max_drawdown(price: pd.Series) -> float:
    peak = price.cummax()
    dd = price / peak - 1.0
    return dd.min()


def annualized_vol(returns: pd.Series) -> float:
    return returns.std() * np.sqrt(252)


def total_return(price: pd.Series) -> float:
    return price.iloc[-1] / price.iloc[0] - 1.0


# -----------------------------
# Main
# -----------------------------

def main():
    price = load_price_series(PORTFOLIO_PATH)

    results = []

    for name, (start, end) in STRESS_WINDOWS.items():
        window_price = price.loc[start:end]

        if len(window_price) < 2:
            continue

        rets = compute_returns(window_price)

        results.append({
            "window": name,
            "start": start,
            "end": end,
            "total_return": total_return(window_price),
            "max_drawdown": max_drawdown(window_price),
            "ann_vol": annualized_vol(rets),
            "obs": len(rets),
        })

    df = pd.DataFrame(results).set_index("window")
    df.to_csv(OUTPUT_DIR / "stress_window_analysis.csv")

    print("Stress window analysis complete.")
    print(df)


if __name__ == "__main__":
    main()
