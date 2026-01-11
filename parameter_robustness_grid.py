import pandas as pd
import numpy as np
from pathlib import Path

BASE_EQUITY = Path("results/portfolio_equity_FINAL.csv")
OUT_PATH = Path("results/robustness_parameter_grid.csv")

VOL_MULTIPLIERS = [0.8, 0.9, 1.0, 1.1, 1.2]
BETA_SHIFTS = [-0.2, -0.1, 0.0, 0.1, 0.2]


def main():
    df = pd.read_csv(BASE_EQUITY, index_col=0, parse_dates=True)
    base = df.iloc[:, 0].pct_change().dropna()

    results = []

    for v in VOL_MULTIPLIERS:
        for b in BETA_SHIFTS:
            adj = base * v * (1 + b)
            equity = (1 + adj).cumprod()

            results.append({
                "vol_mult": v,
                "beta_shift": b,
                "final_equity": equity.iloc[-1],
                "max_drawdown": (equity / equity.cummax() - 1).min()
            })

    out = pd.DataFrame(results)
    out.to_csv(OUT_PATH, index=False)

    print("Parameter robustness grid complete.")
    print(out.sort_values("final_equity", ascending=False).head())


if __name__ == "__main__":
    main()
