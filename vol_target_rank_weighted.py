import pandas as pd
import numpy as np
from pathlib import Path

INPUT_FILE = "results/portfolio_equity_rank_weighted.csv"
OUTPUT_FILE = "results/portfolio_equity_rank_weighted_vol.csv"

TARGET_VOL = 0.12        # 12% annualized target
VOL_WINDOW = 12          # rolling months
MONTHS_PER_YEAR = 12


def main():
    df = pd.read_csv(INPUT_FILE, parse_dates=["date"]).sort_values("date")

    # Compute monthly returns
    df["ret"] = df["equity"].pct_change()

    # Rolling realized volatility (annualized)
    df["vol"] = (
        df["ret"]
        .rolling(VOL_WINDOW)
        .std()
        * np.sqrt(MONTHS_PER_YEAR)
    )

    # Vol targeting scale factor
    df["scale"] = TARGET_VOL / df["vol"]

    # Cap leverage for sanity
    df["scale"] = df["scale"].clip(lower=0.0, upper=1.5)

    # Vol-adjusted returns
    df["adj_ret"] = df["ret"] * df["scale"]

    # Build adjusted equity curve
    df["equity"] = (1 + df["adj_ret"]).cumprod()

    # Output
    out = df[["date", "equity", "scale", "vol"]].dropna()
    Path(OUTPUT_FILE).parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(OUTPUT_FILE, index=False)

    print(f"📈 Vol-targeted rank-weighted equity saved → {OUTPUT_FILE}")
    print(out.tail())


if __name__ == "__main__":
    main()
