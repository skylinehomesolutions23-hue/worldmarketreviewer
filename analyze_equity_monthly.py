import pandas as pd
import numpy as np
from pathlib import Path

EQUITY_FILE = Path("results/equity_curve_monthly.csv")


def main():
    df = pd.read_csv(EQUITY_FILE, parse_dates=["date"])
    df = df.set_index("date")

    returns = df["equity"].pct_change().dropna()

    cagr = (df["equity"].iloc[-1] / df["equity"].iloc[0]) ** (
        12 / len(df)
    ) - 1

    sharpe = (returns.mean() / returns.std()) * np.sqrt(12)

    max_dd = (df["equity"] / df["equity"].cummax() - 1).min()

    total_return = df["equity"].iloc[-1] - df["equity"].iloc[0]

    summary = pd.DataFrame(
        {
            "CAGR": [round(cagr, 4)],
            "Sharpe": [round(sharpe, 4)],
            "Max Drawdown": [round(max_dd, 4)],
            "Total Return": [round(total_return, 2)],
        }
    )

    print(summary)


if __name__ == "__main__":
    main()
