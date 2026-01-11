# performance_stats.py

import pandas as pd
import numpy as np

FILE = "results/benchmark_comparison.csv"
OUT = "results/performance_stats.csv"


def cagr(equity):
    years = len(equity) / 12
    return equity.iloc[-1] ** (1 / years) - 1


def max_drawdown(equity):
    peak = equity.cummax()
    drawdown = equity / peak - 1
    return drawdown.min()


def main():
    df = pd.read_csv(FILE, parse_dates=["date"])

    df["factor_return"] = df["equity"].pct_change()
    df["spy_return"] = df["spy_equity"].pct_change()

    df = df.dropna()

    stats = []

    for label, col in [("Factor", "factor_return"), ("SPY", "spy_return")]:
        stats.append({
            "strategy": label,
            "CAGR": cagr(df[col] + 1),
            "Volatility": df[col].std() * np.sqrt(12),
            "Sharpe": df[col].mean() / df[col].std() * np.sqrt(12),
            "MaxDrawdown": max_drawdown((1 + df[col]).cumprod())
        })

    stats_df = pd.DataFrame(stats)
    stats_df.to_csv(OUT, index=False)

    print("📊 Performance stats saved →", OUT)
    print(stats_df.round(3))


if __name__ == "__main__":
    main()
