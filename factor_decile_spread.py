# factor_decile_spread.py

import pandas as pd
import os

INPUT_FILE = "data/forward_returns.csv"
OUTPUT_FILE = "results/factor_returns.csv"

TOP_N = 2
BOTTOM_N = 2


def main():
    df = pd.read_csv(INPUT_FILE, parse_dates=["date"])

    # Safety check
    required = {"date", "rank", "forward_return"}
    if not required.issubset(df.columns):
        raise RuntimeError("Missing required columns in forward_returns.csv")

    factor_returns = []

    for date, group in df.groupby("date"):
        group = group.dropna(subset=["rank", "forward_return"])

        long_leg = group[group["rank"] <= TOP_N]["forward_return"]
        short_leg = group[group["rank"] > (group["rank"].max() - BOTTOM_N)]["forward_return"]

        if long_leg.empty or short_leg.empty:
            continue

        factor_ret = long_leg.mean() - short_leg.mean()

        factor_returns.append({
            "date": date,
            "long_return": long_leg.mean(),
            "short_return": short_leg.mean(),
            "factor_return": factor_ret
        })

    factor_df = pd.DataFrame(factor_returns).sort_values("date")

    os.makedirs("results", exist_ok=True)
    factor_df.to_csv(OUTPUT_FILE, index=False)

    print(f"✅ Factor returns saved → {OUTPUT_FILE}")
    print(factor_df.head())


if __name__ == "__main__":
    main()
