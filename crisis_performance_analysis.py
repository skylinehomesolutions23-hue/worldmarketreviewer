# crisis_performance_analysis.py

import pandas as pd
import numpy as np
from pathlib import Path
from crisis_windows import CRISIS_WINDOWS
from data_utils import load_price_series

PORT_PATH = "results/portfolio_equity_final_master.csv"
SPY_PATH = "data/SPY.csv"
OUT_DIR = Path("results/crisis")
OUT_DIR.mkdir(parents=True, exist_ok=True)


def max_drawdown(series: pd.Series) -> float:
    roll_max = series.cummax()
    dd = series / roll_max - 1.0
    return dd.min()


def compute_beta(port_ret, spy_ret):
    aligned = pd.concat([port_ret, spy_ret], axis=1).dropna()
    if len(aligned) < 5:
        return np.nan
    cov = np.cov(aligned.iloc[:, 0], aligned.iloc[:, 1])[0, 1]
    return cov / np.var(aligned.iloc[:, 1])


def main():
    port = load_price_series(PORT_PATH)
    spy = load_price_series(SPY_PATH)

    port_ret = port.pct_change()
    spy_ret = spy.pct_change()

    rows = []

    for name, win in CRISIS_WINDOWS.items():
        start, end = win["start"], win["end"]

        p = port.loc[start:end]
        r = port_ret.loc[start:end]
        s = spy_ret.loc[start:end]

        if len(p) < 3:
            continue

        rows.append({
            "crisis": name,
            "start": start,
            "end": end,
            "total_return": p.iloc[-1] / p.iloc[0] - 1,
            "max_drawdown": max_drawdown(p),
            "annual_vol": r.std() * np.sqrt(12),
            "beta_vs_spy": compute_beta(r, s),
            "months": len(p)
        })

    df = pd.DataFrame(rows)
    out = OUT_DIR / "crisis_performance_summary.csv"
    df.to_csv(out, index=False)

    print("Crisis performance analysis complete.")
    print(df)


if __name__ == "__main__":
    main()
