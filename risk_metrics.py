import pandas as pd
import numpy as np
from pathlib import Path

DECAY_DIR = Path("results/decay")
OUT_PATH = DECAY_DIR / "risk_metrics.csv"


def max_drawdown(series):
    cum = (1 + series).cumprod()
    peak = cum.cummax()
    dd = (cum - peak) / peak
    return dd.min()


def main():
    df = pd.read_csv(
        DECAY_DIR / "portfolio_returns.csv",
        parse_dates=["date"]
    )

    r = df["net_return"]

    metrics = {
        "annual_return": r.mean() * 12,
        "annual_vol": r.std() * np.sqrt(12),
        "sharpe": (r.mean() / r.std()) * np.sqrt(12),
        "max_drawdown": max_drawdown(r),
        "win_rate": (r > 0).mean()
    }

    out = pd.DataFrame([metrics])
    out.to_csv(OUT_PATH, index=False)

    print("✅ Risk metrics complete")
    print(out)


if __name__ == "__main__":
    main()
