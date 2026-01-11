import pandas as pd
from pathlib import Path

RESULTS_DIR = Path("results")


def max_drawdown(series):
    roll_max = series.cummax()
    dd = series / roll_max - 1
    return dd.min()


def main():
    file = RESULTS_DIR / "equity_vs_spy.csv"

    if not file.exists():
        raise FileNotFoundError("equity_vs_spy.csv not found")

    df = pd.read_csv(file)

    if len(df) < 2:
        raise ValueError("Not enough data for drawdowns")

    dd = pd.Series(
        {
            "strategy_dd": max_drawdown(df["equity"]),
            "spy_dd": max_drawdown(df["spy_equity"]),
        }
    )

    out = RESULTS_DIR / "drawdowns.csv"
    dd.to_csv(out)

    print("📉 Drawdowns saved →", out)
    print(dd)


if __name__ == "__main__":
    main()
