# backtest_rank_weighted.py
import pandas as pd
import numpy as np

SIGNALS_FILE = "data/signals_rank_filtered.csv"
RETURNS_FILE = "data/forward_returns.csv"
OUT_FILE = "results/portfolio_equity_rank_weighted.csv"

def main():
    sig = pd.read_csv(SIGNALS_FILE)
    ret = pd.read_csv(RETURNS_FILE)

    df = sig.merge(ret, on=["date", "ticker", "rank"], how="inner")

    # rank-based weights (inverse sqrt)
    df["raw_weight"] = 1 / np.sqrt(df["rank"])

    # normalize weights each month
    df["weight"] = df.groupby("date")["raw_weight"].transform(
        lambda x: x / x.sum()
    )

    df["weighted_return"] = df["weight"] * df["forward_return"]

    monthly = (
        df.groupby("date")["weighted_return"]
        .sum()
        .reset_index()
        .sort_values("date")
    )

    monthly["equity"] = (1 + monthly["weighted_return"]).cumprod()

    monthly[["date", "equity"]].to_csv(OUT_FILE, index=False)

    print("📈 Rank-weighted equity saved →", OUT_FILE)
    print(monthly.head())

if __name__ == "__main__":
    main()
