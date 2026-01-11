# portfolio_weighted_by_rank.py
import pandas as pd

SIGNALS = "data/signals.csv"
RETURNS = "data/forward_returns.csv"
OUT = "results/portfolio_weighted_by_rank.csv"

def main():
    sig = pd.read_csv(SIGNALS, parse_dates=["date"])
    ret = pd.read_csv(RETURNS, parse_dates=["date"])

    df = sig.merge(ret, on=["date", "ticker", "rank"])

    df["weight"] = df["rank"] / df.groupby("date")["rank"].transform("sum")
    df["weighted_return"] = df["weight"] * df["forward_return"]

    equity = (
        df.groupby("date")["weighted_return"]
        .sum()
        .add(1)
        .cumprod()
        .reset_index(name="equity")
    )

    equity.to_csv(OUT, index=False)
    print(f"📈 Rank-weighted equity saved → {OUT}")

if __name__ == "__main__":
    main()
