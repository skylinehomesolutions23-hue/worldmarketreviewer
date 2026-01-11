import pandas as pd
import numpy as np
from pathlib import Path

EQUITY_PATH = Path("results/portfolio_equity_FINAL.csv")
OUT_PATH = Path("results/drawdown_clusters.csv")

CLUSTER_THRESHOLD = -0.05  # 5% drawdown events


def main():
    df = pd.read_csv(EQUITY_PATH, index_col=0, parse_dates=True)
    equity = df.iloc[:, 0]

    dd = equity / equity.cummax() - 1
    drawdowns = dd[dd < CLUSTER_THRESHOLD]

    clusters = []
    current = []

    for date, value in drawdowns.items():
        if not current:
            current = [(date, value)]
            continue

        prev_date = current[-1][0]
        if (date - prev_date).days <= 31:
            current.append((date, value))
        else:
            clusters.append(current)
            current = [(date, value)]

    if current:
        clusters.append(current)

    summary = []
    for c in clusters:
        summary.append({
            "start": c[0][0],
            "end": c[-1][0],
            "length": len(c),
            "worst_dd": min(v for _, v in c)
        })

    out = pd.DataFrame(summary)
    out.to_csv(OUT_PATH, index=False)

    print("Drawdown clustering analysis complete.")
    print(out.sort_values("worst_dd").head())


if __name__ == "__main__":
    main()
