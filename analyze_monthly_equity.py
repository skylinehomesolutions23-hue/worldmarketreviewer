# analyze_monthly_equity.py
import pandas as pd
import numpy as np
from pathlib import Path

RESULTS_DIR = Path("results")


def analyze():
    path = RESULTS_DIR / "monthly_equity.csv"
    if not path.exists():
        raise FileNotFoundError("monthly_equity.csv not found. Run backtest first.")

    df = pd.read_csv(path)
    returns = df["return"]

    cagr = (df["equity"].iloc[-1]) ** (12 / len(df)) - 1
    sharpe = np.sqrt(12) * returns.mean() / returns.std()
    drawdown = df["equity"] / df["equity"].cummax() - 1

    stats = pd.DataFrame([{
        "CAGR": round(cagr, 4),
        "Sharpe": round(sharpe, 2),
        "Max Drawdown": round(drawdown.min(), 4),
    }])

    print(stats)
    return stats


if __name__ == "__main__":
    analyze()
