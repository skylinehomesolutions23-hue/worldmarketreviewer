# crisis_attribution_report.py

import pandas as pd
import numpy as np
from pathlib import Path
from crisis_windows import CRISIS_WINDOWS
from data_utils import load_price_series

PORT_PATH = "results/portfolio_equity_final_master.csv"
REGIME_PATH = "results/regime_monthly.csv"

OUT_DIR = Path("results/crisis")
OUT_DIR.mkdir(parents=True, exist_ok=True)


def main():
    port = load_price_series(PORT_PATH)
    reg = pd.read_csv(REGIME_PATH, index_col=0, parse_dates=True)

    rows = []

    for name, win in CRISIS_WINDOWS.items():
        start, end = win["start"], win["end"]

        p = port.loc[start:end]
        r = p.pct_change().dropna()
        g = reg.loc[start:end].iloc[:, 0]

        if len(p) < 3:
            continue

        rows.append({
            "crisis": name,
            "avg_return": r.mean(),
            "worst_month": r.min(),
            "positive_months_pct": (r > 0).mean(),
            "risk_on_pct": (g == "RISK-ON").mean(),
            "cash_pct": (g != "RISK-ON").mean(),
            "observations": len(r)
        })

    df = pd.DataFrame(rows)
    out = OUT_DIR / "crisis_attribution_report.csv"
    df.to_csv(out, index=False)

    print("Crisis attribution report complete.")
    print(df)


if __name__ == "__main__":
    main()
