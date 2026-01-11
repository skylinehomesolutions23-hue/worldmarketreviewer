import pandas as pd
import numpy as np
import sys

FILE = "results/cost_stress_test.csv"


def performance_stats(equity: pd.Series) -> dict:
    returns = equity.pct_change().dropna()

    if returns.empty:
        return {
            "CAGR": np.nan,
            "Sharpe": np.nan,
            "Max Drawdown": np.nan,
            "Total Return": np.nan,
        }

    years = len(returns) / 12
    cagr = (equity.iloc[-1] / equity.iloc[0]) ** (1 / years) - 1

    sharpe = (
        np.sqrt(12) * returns.mean() / returns.std()
        if returns.std() != 0
        else np.nan
    )

    rolling_max = equity.cummax()
    drawdown = (equity / rolling_max) - 1
    max_dd = drawdown.min()

    total_return = equity.iloc[-1] / equity.iloc[0]

    return {
        "CAGR": round(cagr, 4),
        "Sharpe": round(sharpe, 4),
        "Max Drawdown": round(max_dd, 4),
        "Total Return": round(total_return, 4),
    }


def main():
    df = pd.read_csv(FILE, index_col=0, parse_dates=True)

    results = []

    for col in df.columns:
        stats = performance_stats(df[col])
        stats["Scenario"] = col
        results.append(stats)

    out = pd.DataFrame(results).set_index("Scenario")
    out.to_csv("results/cost_stress_summary.csv")

    print("\n📊 COST STRESS TEST SUMMARY")
    print("=" * 40)
    print(out)
    print("\n💾 Saved → results/cost_stress_summary.csv")


if __name__ == "__main__":
    main()
